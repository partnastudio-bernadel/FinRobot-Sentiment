import sys
import os
import json
import argparse
from dotenv import load_dotenv

# Resolve script paths and ensure the sentiment directory is in Python's lookup path
script_dir = os.path.dirname(os.path.abspath(__file__))
sentiment_dir = os.path.dirname(script_dir)

if sentiment_dir not in sys.path:
    sys.path.insert(0, sentiment_dir)

# Import package modules
try:
    from functions.aggregator.aggregator import fetch_aggregate_all_news
    from functions.utils.read_and_clean import read_file_content, extract_and_clean_response
    from functions.utils.build import build_vector_store
    from functions.utils.config import generate_config
    from functions.tools.prepare_articles import prepare_articles, assign_label
    from functions.agents import (
        create_scorer_agent,
        create_cio_agent,
        create_textual_inertia_agent,
        create_tension_extractor_agent,
        create_scribe_agent
    )
    from functions.tools.openbb import fetch_etf_holdings_from_openbb
    from functions.tools.edgar_tools import get_sec_10k_section
    from functions.tools.transcript_tools import fetch_and_split_transcript
    from functions.utils.compliance_logger import log_compliance_event
    from functions.utils.formulas import calculate_raw_sentiment, calculate_portfolio_sentiment, normalize_weights
    from functions.tools.custom_reply import extract_json_array, merge_scored_results
    from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
    from autogen import UserProxyAgent, register_function
except ImportError as e:
    print(f"Error importing required sentiment modules: {e}", file=sys.stderr)
    print("Ensure you have activated your virtual environment and installed the dependencies.", file=sys.stderr)
    sys.exit(1)


def run_sentiment_analysis(
    ticker: str,
    limit: int = 5,
    holdings: int = 5,
    csv_path: str = None,
    env_path: str = None
) -> dict:
    """
    Orchestrates the simplified sentiment analysis and reading workers workflow for a ticker or ETF.
    """
    # 1. Resolve configuration and resource paths
    if env_path is None:
        env_path = os.path.join(sentiment_dir, ".env.local")
        if not os.path.exists(env_path):
            env_path = os.path.join(sentiment_dir, ".env")
            
    if csv_path is None:
        csv_path = os.path.join(sentiment_dir, "data", "financial_sentiment.csv")
        
    prompt_dir = os.path.join(sentiment_dir, "prompts")
    schema_dir = os.path.join(sentiment_dir, "schema_json")

    # Verify that essential paths exist before proceeding
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Configuration file not found at: {env_path}")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Calibration data CSV not found at: {csv_path}")

    # 2. Load environment variables
    load_dotenv(env_path, override=True)
    
    nvidia_embedding_model = os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/nv-embed-v1").strip('"\' ')
    nvidia_api_key = os.getenv("NVIDIA_API_KEY", "").strip('"\' ')
    nvidia_api_endpoint = os.getenv("NVIDIA_API_ENDPOINT", "https://integrate.api.nvidia.com/v1").strip('"\' ')
    
    if not nvidia_api_key:
        raise ValueError("NVIDIA_API_KEY is not set in the environment configuration.")

    # 3. Setup embeddings & LLM configurations
    embeddings = NVIDIAEmbeddings(
        model=nvidia_embedding_model,
        nvidia_api_key=nvidia_api_key,
        base_url=nvidia_api_endpoint
    )
    
    # Setup configs: LLM config for Scorer and base config for CIO
    default_env_local = os.path.join(sentiment_dir, ".env.local")
    default_env = os.path.join(sentiment_dir, ".env")
    if env_path in (default_env_local, default_env):
        from functions import llm_config, base_llm_config
    else:
        nvidia_base_model = os.getenv("NVIDIA_TOOLING_MODEL", "").strip('"\' ')
        hf_api_key = os.getenv("HUGGINGFACE_API_KEY", "").strip('"\' ')
        hf_model_name = os.getenv("HUGGINGFACE_MODEL_NAME_FEATHERLESS", "curiousily/Llama-3-8B-Instruct-Finance-RAG").strip('"\' ')
        hf_base_url = os.getenv("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/v1").strip('"\' ')
        
        if not hf_api_key:
            raise ValueError("HUGGINGFACE_API_KEY is not set in the environment configuration.")
            
        config_list = generate_config(hf_model_name, hf_base_url, hf_api_key)
        base_config_list = generate_config(nvidia_base_model, nvidia_api_endpoint, nvidia_api_key)
        
        llm_config = {"config_list": config_list, "model": hf_model_name}
        base_llm_config = {"config_list": base_config_list, "model": nvidia_base_model}

    # Setup Kimi configuration for the reading and compliance workers
    nvidia_base_model_alt = os.getenv("NVIDIA_BASE_MODEL_ALT", "moonshotai/kimi-k2.6").strip('"\' ')
    kimi_config_list = generate_config(nvidia_base_model_alt, nvidia_api_endpoint, nvidia_api_key)
    kimi_llm_config = {"config_list": kimi_config_list, "model": nvidia_base_model_alt}

    # 4. Build vector store for calibration examples
    db = build_vector_store(csv_path, embeddings, limit_rows=300)

    # 5. Create AutoGen Agents
    user_proxy = UserProxyAgent(
        name="User_Proxy",
        human_input_mode="NEVER",
        is_termination_msg=lambda x: x.get("content", "") and "TERMINATE" in x.get("content", ""),
        max_consecutive_auto_reply=15,
        code_execution_config={"use_docker": False}
    )
    
    scorer_agent = create_scorer_agent(
        prompt_path=os.path.join(prompt_dir, "sentiment_prompt.txt"),
        schema_path=os.path.join(schema_dir, "scorer_schema.json"),
        llm_config=llm_config
    )
    
    cio_agent = create_cio_agent(
        prompt_path=os.path.join(prompt_dir, "cio_prompt.txt"),
        schema_path=os.path.join(schema_dir, "sentiment_schema.json"),
        output_schema_path=os.path.join(schema_dir, "cio_output_schema.json"),
        scored_articles_path=os.path.join(schema_dir, "cio_scored_articles.json"),
        llm_config=base_llm_config
    )

    # Instantiate Kimi reading workers and compliance documentarian
    textual_inertia_agent = create_textual_inertia_agent(
        prompt_path=os.path.join(prompt_dir, "textual_inertia_prompt.txt"),
        llm_config=kimi_llm_config
    )

    tension_extractor_agent = create_tension_extractor_agent(
        prompt_path=os.path.join(prompt_dir, "tension_extractor_prompt.txt"),
        llm_config=kimi_llm_config
    )

    scribe_agent = create_scribe_agent(
        prompt_path=os.path.join(prompt_dir, "scribe_prompt.txt"),
        llm_config=kimi_llm_config
    )

    # 5b. Strip name parameter hook from NIM payloads
    for agent in [user_proxy, scorer_agent, cio_agent, textual_inertia_agent, tension_extractor_agent, scribe_agent]:
        from functions.utils.read_and_clean import strip_name_hook
        agent.register_hook(
            hookable_method="process_all_messages_before_reply",
            hook=strip_name_hook
        )

    # 6. Register math tools directly to the CIO Agent (User_Proxy as executor)
    register_function(
        calculate_raw_sentiment,
        caller=cio_agent,
        executor=user_proxy,
        name="calculate_raw_sentiment",
        description="Calculates the confidence-weighted average sentiment score of scored articles for a single asset."
    )

    register_function(
        calculate_portfolio_sentiment,
        caller=cio_agent,
        executor=user_proxy,
        name="calculate_portfolio_sentiment",
        description="Aggregates effective ticker sentiments by portfolio holding weight."
    )

    register_function(
        normalize_weights,
        caller=cio_agent,
        executor=user_proxy,
        name="normalize_weights",
        description="Normalizes a dictionary of weights so that their sum equals 1.0."
    )

    register_function(
        assign_label,
        caller=cio_agent,
        executor=user_proxy,
        name="assign_label",
        description="Assigns a sentiment classification label based on the calculated sentiment score."
    )

    # 7. Step 1: ETF Decomposition via OpenBB directly in Python
    print("\n[+] Step 1: Running ETF Decomposition check...")
    df_holdings = fetch_etf_holdings_from_openbb(ticker)
    
    is_etf = False
    constituents = []
    decomp_data = {}
    
    if not df_holdings.empty:
        # Sort holdings descending by weight
        df_holdings = df_holdings.sort_values(by="fund_weight", ascending=False)
        candidate_constituents = df_holdings.to_dict(orient="records")
        
        # Filter out invalid or self-referential constituents
        candidate_constituents = [
            c for c in candidate_constituents
            if c.get("ticker") and str(c.get("ticker")).strip().upper() != ticker.upper()
        ]
        
        if len(candidate_constituents) > 0:
            constituents = candidate_constituents[:holdings]
            is_etf = True
            decomp_data = {
                "ticker": ticker,
                "is_etf": True,
                "error_flag": False,
                "constituents": [
                    {"ticker": c["ticker"], "weight": float(c["fund_weight"])}
                    for c in constituents
                ]
            }

    if not is_etf:
        decomp_data = {
            "ticker": ticker,
            "is_etf": False,
            "error_flag": False,
            "constituents": []
        }

    # 8. Step 2: Fetch and Prepare Articles
    all_articles = []
    if is_etf and constituents:
        print(f"[+] Decomposed ETF. Top {len(constituents)} constituents to analyze: {[c['ticker'] for c in constituents]}")
        for const in constituents:
            c_ticker = const["ticker"]
            print(f"[*] Fetching news for constituent: {c_ticker}...")
            try:
                df_c_news = fetch_aggregate_all_news(symbol=c_ticker, limit=100)
                if df_c_news.empty:
                    print(f"[-] No articles found for constituent {c_ticker}. Skipping.")
                    continue
                prepared = prepare_articles(df_c_news, db, limit=limit)
                for art in prepared:
                    art["ticker"] = c_ticker
                all_articles.extend(prepared)
            except Exception as ex:
                print(f"[-] Error processing constituent {c_ticker}: {ex}. Skipping.")
    else:
        print(f"[*] Ticker {ticker} is a single stock or failed decomposition. Processing fallback...")
        try:
            df_news = fetch_aggregate_all_news(symbol=ticker, limit=100)
            if not df_news.empty:
                prepared = prepare_articles(df_news, db, limit=limit)
                for art in prepared:
                    art["ticker"] = ticker
                all_articles.extend(prepared)
        except Exception as ex:
            print(f"[-] Error processing ticker {ticker}: {ex}.")

    if not all_articles:
        print("[-] No news articles collected. Returning empty report.")
        return {
            "ticker": ticker,
            "error": "No news articles collected.",
            "metrics": {
                "sentiment_score": 0.0,
                "label": "Neutral"
            }
        }

    # 9. Step 3: Batch scoring using Scorer Agent in cycles of 5
    batch_size = 5
    batch_results = []
    
    for i in range(0, len(all_articles), batch_size):
        batch = all_articles[i:i + batch_size]
        print(f"[*] Batching scoring pipeline: processing articles {i+1} to {min(i+batch_size, len(all_articles))} of {len(all_articles)}")
        
        user_proxy.initiate_chat(
            scorer_agent,
            message=(
                "Please score the following articles according to your instructions:\n\n"
                f"{json.dumps(batch, indent=2)}\n\n"
                "Respond with the list of scored articles."
            ),
            clear_history=True,
            silent=True
        )
        
        summary_content = extract_and_clean_response(user_proxy, scorer_agent, is_json=True)
        scored_data = extract_json_array(summary_content)
        if scored_data is not None:
            batch_results.append(scored_data)
        else:
            try:
                clean_content = summary_content
                if clean_content.endswith("TERMINATE"):
                    clean_content = clean_content[:-9].strip()
                batch_results.append(json.loads(clean_content))
            except Exception as e:
                print(f"[!] Error parsing batch response: {e}. Raw content: {summary_content}")

    # Merge batch results
    merged_result = merge_scored_results(batch_results)
    scorer_summary = json.dumps(merged_result, indent=2)

    # 10. Step 4: Run Unstructured Reading Workers Layer (Textual Inertia & Analyst Tension)
    # To optimize execution, we query files and transcripts for constituents (or target ticker).
    # Since these are cognitive tasks, we run them via the dedicated Kimi agents.
    print("\n[+] Step 2: Running Unstructured Reading Workers Layer...")
    
    tickers_to_query = [c["ticker"] for c in constituents] if is_etf else [ticker]
    indicators_report_data = {}
    
    for t_symbol in tickers_to_query:
        print(f"[*] Analyzing qualitative indicators for asset: {t_symbol}...")
        indicators_report_data[t_symbol] = {
            "textual_inertia": 0.0,
            "textual_inertia_reason": "No data available.",
            "tension": 0.0,
            "tension_reason": "No data available."
        }
        
        # A. Item 1A (Risk Factors) Textual Inertia (Lazy Prices)
        try:
            current_year = 2024
            prev_year = 2023
            current_sec = get_sec_10k_section(t_symbol, current_year, "1A")
            prev_sec = get_sec_10k_section(t_symbol, prev_year, "1A")
            
            if current_sec and prev_sec and not current_sec.startswith("Risk Factors") and len(current_sec) > 500:
                print(f"[*] Running Textual Inertia Agent on consecutive filings for {t_symbol}...")
                user_proxy.initiate_chat(
                    textual_inertia_agent,
                    message=(
                        f"Please analyze the Risk Factors (Item 1A) text deviations for ticker: {t_symbol}\n\n"
                        f"--- CURRENT YEAR {current_year} RISK FACTORS ---\n"
                        f"{current_sec[:40000]}\n\n"  # Slice to fit within safe API thresholds
                        f"--- PREVIOUS YEAR {prev_year} RISK FACTORS ---\n"
                        f"{prev_sec[:40000]}\n\n"
                    ),
                    clear_history=True,
                    silent=True
                )
                res_inertia = extract_and_clean_response(user_proxy, textual_inertia_agent, is_json=True)
                parsed_inertia = json.loads(res_inertia)
                indicators_report_data[t_symbol]["textual_inertia"] = float(parsed_inertia.get("modification_score", 0.0))
                indicators_report_data[t_symbol]["textual_inertia_reason"] = parsed_inertia.get("reasoning_summary", "")
            else:
                indicators_report_data[t_symbol]["textual_inertia_reason"] = "Risk factors filings unavailable."
        except Exception as e:
            print(f"[!] Warning: failed to compute Textual Inertia for {t_symbol}: {e}")
            indicators_report_data[t_symbol]["textual_inertia_reason"] = f"Extraction failed: {e}"

        # B. Analyst Q&A Tension Extractor
        try:
            transcript_data = fetch_and_split_transcript(t_symbol)
            qa_block = transcript_data.get("qa", "")
            
            if qa_block and len(qa_block) > 500:
                print(f"[*] Running Q&A Tension Extractor Agent on earnings call for {t_symbol}...")
                user_proxy.initiate_chat(
                    tension_extractor_agent,
                    message=(
                        f"Please analyze corporate call Q&A tension for ticker: {t_symbol}\n\n"
                        f"--- ANALYST Q&A BLOCK ---\n"
                        f"{qa_block[:40000]}\n\n"
                    ),
                    clear_history=True,
                    silent=True
                )
                res_tension = extract_and_clean_response(user_proxy, tension_extractor_agent, is_json=True)
                parsed_tension = json.loads(res_tension)
                indicators_report_data[t_symbol]["tension"] = float(parsed_tension.get("tension_score", 0.0))
                indicators_report_data[t_symbol]["tension_reason"] = parsed_tension.get("reasoning_summary", "")
            else:
                indicators_report_data[t_symbol]["tension_reason"] = "Earnings call Q&A transcript unavailable."
        except Exception as e:
            print(f"[!] Warning: failed to extract Analyst Q&A tension for {t_symbol}: {e}")
            indicators_report_data[t_symbol]["tension_reason"] = f"Extraction failed: {e}"

    # Format the indicators context
    indicators_report_str = "--- QUALITATIVE INDICATORS (TEXTUAL INERTIA & TENSION) ---\n"
    for t_symbol, data in indicators_report_data.items():
        indicators_report_str += (
            f"Asset: {t_symbol}\n"
            f"  - Textual Inertia (Lazy Prices) Score: {data['textual_inertia']} ({data['textual_inertia_reason']})\n"
            f"  - Analyst Q&A Tension Score: {data['tension']} ({data['tension_reason']})\n\n"
        )

    # 11. Step 5: Inject direct context and run Consolidated Senior Analyst (CIO) Chat
    if is_etf and constituents:
        decomp_report = (
            f"ETF Decomposition Report:\n"
            f"{json.dumps(decomp_data, indent=2)}"
        )
    else:
        decomp_report = (
            f"ETF Decomposition Report: This asset is a single stock. No constituents found."
        )
        
    combined_message = (
        f"You are requested to analyze the sentiment for ticker: {ticker}\n\n"
        f"Here is the data retrieved by the pipeline:\n\n"
        f"--- ETF DECOMPOSITION DATA ---\n"
        f"{decomp_report}\n\n"
        f"--- SCORED NEWS ARTICLES DATA ---\n"
        f"{scorer_summary}\n\n"
        f"{indicators_report_str}\n"
        "Now, use your registered tools (normalize_weights, calculate_raw_sentiment, "
        "calculate_portfolio_sentiment, assign_label) to perform the mathematical calculations "
        "and generate the final JSON report according to your rules."
    )

    print("\n[+] Initiating Consolidated Senior Analyst (CIO) Chat...")
    user_proxy.initiate_chat(
        cio_agent,
        message=combined_message,
        clear_history=True
    )

    # 12. Extract and clean final report
    final_report_msg = extract_and_clean_response(user_proxy, cio_agent, is_json=True)
    
    try:
        final_report = json.loads(final_report_msg)
    except json.JSONDecodeError as e:
        final_report = {
            "ticker": ticker,
            "error": "Failed to parse CIO agent response as JSON.",
            "details": str(e),
            "raw_output": final_report_msg
        }
        return final_report

    # 13. Step 6: Simulate compliance limit validation and trigger Scribe manual override narrative
    print("\n[+] Step 3: Running compliance allocation gateway checks...")
    
    # Calculate baseline vs proposed weights based on sentiment tilt
    # Formula: proposed_weight = base_weight * (1.0 + alpha_t * sentiment_score)
    # If the drift is > 15% (0.15), trigger Scribe Agent to write override justifications to compliance logs
    alpha_t = 0.5
    aggregate_score = final_report.get("aggregate_score", 0.0)
    
    if is_etf and constituents:
        base_weights = {c["ticker"]: float(c["weight"]) for c in constituents}
        normalized_base = normalize_weights(base_weights)
        
        # Calculate drift per asset
        violations = []
        for t_symbol, w_base in normalized_base.items():
            t_news_sentiment = 0.0
            # Retrieve specific constituent score if present in merged scored results
            if isinstance(merged_result, list):
                for r in merged_result:
                    if r.get("ticker") == t_symbol:
                        t_news_sentiment = float(calculate_raw_sentiment(r))
                        break
            elif isinstance(merged_result, dict) and merged_result.get("ticker") == t_symbol:
                t_news_sentiment = float(calculate_raw_sentiment(merged_result))
                
            w_proposed = w_base * (1.0 + alpha_t * t_news_sentiment)
            drift = abs(w_proposed - w_base)
            if drift > 0.15:
                violations.append({
                    "ticker": t_symbol,
                    "base": w_base,
                    "proposed": w_proposed,
                    "drift": drift
                })
    else:
        w_base = 1.0
        w_proposed = w_base * (1.0 + alpha_t * aggregate_score)
        drift = abs(w_proposed - w_base)
        violations = []
        if drift > 0.15:
            violations.append({
                "ticker": ticker,
                "base": w_base,
                "proposed": w_proposed,
                "drift": drift
            })

    if violations:
        print(f"[Compliance] 15% Allocation Drift Limit Violated! Active violations count: {len(violations)}")
        for v in violations:
            print(f"  - Asset {v['ticker']}: Proposed Weight {v['proposed']:.4f} (Base: {v['base']:.4f}, Drift: {v['drift']*100:.2f}%)")
            
        print("[Compliance] Spawning Thesis-CoT Scribe Agent to generate justification narrative...")
        
        # Trigger Thesis-CoT Scribe Agent to write legal overrides justification
        user_proxy.initiate_chat(
            scribe_agent,
            message=(
                f"Compliance warning triggered. Please write an override justification for the following drift:\n"
                f"Violations details: {json.dumps(violations, indent=2)}\n"
                f"Qualitative Indicators: {json.dumps(indicators_report_data, indent=2)}\n"
                f"Pipeline Consolidated Report: {json.dumps(final_report, indent=2)}\n"
                f"Investor override requested reason: Institutional portfolio reallocation based on alpha indicators."
            ),
            clear_history=True,
            silent=True
        )
        
        res_scribe = extract_and_clean_response(user_proxy, scribe_agent, is_json=True)
        try:
            parsed_scribe = json.loads(res_scribe)
            compliance_thesis = parsed_scribe.get("compliance_thesis", "Override approved based on qualitative indicator drift.")
            
            # Log the override event to local file logs
            log_compliance_event(
                event_type="OVERRIDE",
                metadata={
                    "ticker": ticker,
                    "violations": violations,
                    "indicators": indicators_report_data,
                    "compliance_thesis": compliance_thesis,
                    "status": "APPROVED"
                }
            )
            
            # Enrich final report payload with compliance thesis narrative
            final_report["compliance_override"] = {
                "limit_violated": "15% allocation drift limit exceeded",
                "justification": compliance_thesis,
                "status": "APPROVED_AND_LOGGED"
            }
        except Exception as ex:
            print(f"[!] Warning: failed to parse Scribe justification JSON: {ex}. Logging raw string.")
            log_compliance_event(
                event_type="OVERRIDE_PARSE_FAILURE",
                metadata={
                    "ticker": ticker,
                    "raw_scribe_output": res_scribe,
                    "violations": violations,
                    "status": "APPROVED_WITH_WARNING"
                }
            )
            final_report["compliance_override"] = {
                "limit_violated": "15% allocation drift limit exceeded",
                "justification": "Manual compliance override approved.",
                "status": "APPROVED_WITH_WARNING"
            }
    else:
        print("[Compliance] Allocation drift gateway validation passed successfully (drift <= 15%).")

    return final_report


def main():
    parser = argparse.ArgumentParser(
        description="CLI utility for running the FinRobot Agent-to-Agent News Sentiment Analyzer."
    )
    parser.add_argument(
        "--ticker", "-t",
        type=str,
        default="AAPL",
        help="Stock ticker symbol to analyze (default: AAPL)."
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=5,
        help="Max number of news articles to retrieve and score (default: 5)."
    )
    parser.add_argument(
        "--csv", "-c",
        type=str,
        default=None,
        help="Path to calibration CSV file (default: data/financial_sentiment.csv)."
    )
    parser.add_argument(
        "--holdings", "-k",
        type=int,
        default=5,
        help="Number of top ETF holdings to analyze if ticker is an ETF (default: 5)."
    )
    parser.add_argument(
        "--env", "-e",
        type=str,
        default=None,
        help="Path to environment file (default: .env.local)."
    )
    
    args = parser.parse_args()
    
    print(f"Starting news sentiment analysis for {args.ticker} (Limit: {args.limit}, Holdings: {args.holdings})...")
    
    try:
        report = run_sentiment_analysis(
            ticker=args.ticker,
            limit=args.limit,
            holdings=args.holdings,
            csv_path=args.csv,
            env_path=args.env
        )
        print("\n================ SENTIMENT ANALYSIS REPORT ================")
        print(json.dumps(report, indent=2))
    except Exception as e:
        print(f"\n[Error] Failed to complete analysis: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

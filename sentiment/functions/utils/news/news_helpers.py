import os
import sys
import json
from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from functions.utils.common.build import build_vector_store
from functions.utils.common.config import generate_config
from functions.tools.openbb import fetch_etf_holdings_from_openbb
from functions.aggregator.aggregator import fetch_aggregate_all_news
from functions.tools.prepare_articles import prepare_articles
from functions.utils.common.read_and_clean import extract_and_clean_response
from functions.tools.custom_reply import extract_json_array, merge_scored_results
from functions.tools.edgar_tools import get_sec_10k_section
from functions.tools.transcript_tools import fetch_and_split_transcript
from functions.utils.math.formulas import normalize_weights, calculate_raw_sentiment
from functions.utils.logging.compliance_logger import log_compliance_event

# Resolve sentiment directory relative to this helper file: sentiment/functions/utils/news/news_helpers.py
news_dir = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.dirname(news_dir)
functions_dir = os.path.dirname(utils_dir)
sentiment_dir = os.path.dirname(functions_dir)

def setup_clients_and_embeddings(env_path: str = None, csv_path: str = None) -> tuple:
    """Resolves configuration paths, loads environment variables, and builds calibration database."""
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

    # Load environment variables
    load_dotenv(env_path, override=True)
    
    nvidia_embedding_model = os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/nv-embed-v1").strip('"\' ')
    nvidia_api_key = os.getenv("NVIDIA_API_KEY", "").strip('"\' ')
    nvidia_api_endpoint = os.getenv("NVIDIA_API_ENDPOINT", "https://integrate.api.nvidia.com/v1").strip('"\' ')
    
    if not nvidia_api_key:
        raise ValueError("NVIDIA_API_KEY is not set in the environment configuration.")

    # Setup embeddings & LLM configurations
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

    # Intercept and override deprecated Hugging Face model in-memory (comply with "No edits to env files" rule)
    def override_deprecated_model(config):
        if not config:
            return config
        # Make a copy to avoid mutating global module variables
        config = config.copy()
        model_name = config.get("model", "")
        if "curiousily/Llama-3-8B-Instruct-Finance-RAG" in model_name:
            config["model"] = model_name.replace("curiousily/Llama-3-8B-Instruct-Finance-RAG", "meta-llama/Meta-Llama-3-8B-Instruct")
        if "config_list" in config:
            config["config_list"] = [item.copy() for item in config["config_list"]]
            for item in config["config_list"]:
                item_model = item.get("model", "")
                if "curiousily/Llama-3-8B-Instruct-Finance-RAG" in item_model:
                    item["model"] = item_model.replace("curiousily/Llama-3-8B-Instruct-Finance-RAG", "meta-llama/Meta-Llama-3-8B-Instruct")
        return config

    llm_config = override_deprecated_model(llm_config)

    # Setup Kimi configuration for the reading and compliance workers
    nvidia_base_model_alt = os.getenv("NVIDIA_BASE_MODEL_ALT", "moonshotai/kimi-k2.6").strip('"\' ')
    kimi_config_list = generate_config(nvidia_base_model_alt, nvidia_api_endpoint, nvidia_api_key)
    kimi_llm_config = {"config_list": kimi_config_list, "model": nvidia_base_model_alt}

    # Build vector store for calibration examples
    db = build_vector_store(csv_path, embeddings, limit_rows=300)

    return db, llm_config, base_llm_config, kimi_llm_config, prompt_dir, schema_dir


def fetch_and_decompose_holdings(
    ticker: str,
    holdings: int,
    limit: int,
    db
) -> tuple:
    """Checks ETF decomposition and fetches news articles for the target ticker or its constituents."""
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

    # Fetch and Prepare Articles
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

    return is_etf, constituents, decomp_data, all_articles


def batch_score_articles(
    all_articles: list,
    scorer_agent,
    user_proxy
) -> tuple:
    """Scores news articles in batches of 5 using the Scorer Agent."""
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
    return merged_result, scorer_summary


def execute_reading_workers(
    tickers_to_query: list,
    user_proxy,
    textual_inertia_agent,
    tension_extractor_agent
) -> dict:
    """Runs Unstructured Reading Workers (Textual Inertia and Q&A Tension) for target tickers."""
    print("\n[+] Step 2: Running Unstructured Reading Workers Layer...")
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

    return indicators_report_data


def validate_compliance_limits(
    ticker: str,
    is_etf: bool,
    constituents: list,
    final_report: dict,
    merged_result,
    indicators_report_data: dict,
    scribe_agent,
    user_proxy
) -> dict:
    """Simulates compliance limit validation (L1 drift check) and triggers Thesis-CoT Scribe override justification if drift > 15%."""
    print("\n[+] Step 3: Running compliance allocation gateway checks...")
    
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





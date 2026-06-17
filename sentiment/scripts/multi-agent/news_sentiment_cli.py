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
    from functions.agents import create_scorer_agent, create_cio_agent, create_decomposition_agent
    from functions.tools.openbb import fetch_etf_holdings_from_openbb
    from functions.utils.formulas import calculate_raw_sentiment, calculate_portfolio_sentiment, normalize_weights
    from functions.tools.custom_reply import custom_nested_chat_reply, extract_json_array
    from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
    from autogen import UserProxyAgent, register_function, initiate_chats
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
    Orchestrates the multi-agent sentiment analysis workflow for a given ticker or ETF.
    
    This function is designed to be easily imported and reused by external systems, 
    such as FastAPI endpoints or background task queue workers.
    
    Args:
        ticker: The stock or ETF ticker symbol (e.g., 'AAPL', 'SPY').
        limit: The number of top news articles to fetch and score per entity.
        holdings: The number of top constituents to analyze if ticker is an ETF.
        csv_path: Absolute or relative path to the calibration examples CSV.
        env_path: Absolute or relative path to the env file containing API keys.
        
    Returns:
        A dictionary containing the parsed sentiment analysis report.
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
    load_dotenv(env_path)
    
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
    
    # If using the default env_path, load from central functions package
    default_env_local = os.path.join(sentiment_dir, ".env.local")
    default_env = os.path.join(sentiment_dir, ".env")
    if env_path in (default_env_local, default_env):
        from functions import llm_config, base_llm_config
    else:
        # Re-generate configs based on the custom env file loaded above
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
    
    decomp_agent = create_decomposition_agent(
        prompt_path=os.path.join(prompt_dir, "decomposition_prompt.txt"),
        schema_path=os.path.join(schema_dir, "decomposition_schema.json"),
        example_path=os.path.join(schema_dir, "decomposition_example.json"),
        llm_config=llm_config
    )

    # Register tools
    register_function(
        fetch_etf_holdings_from_openbb,
        caller=decomp_agent,
        executor=cio_agent,
        name="fetch_etf_holdings_from_openbb",
        description="Fetch underlying constituents and weights for an ETF tracker."
    )

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

    # 6. Configure custom nested chat reply handler
    def news_sentiment_custom_reply(chat_queue, recipient, messages, sender, config):
        """Custom reply handler that orchestrates ETF decomposition and constituent batch scoring."""
        # 1. First-Turn Loop Guard (prevent re-running news pipeline on tool execution replies)
        if len(messages) > 1:
            return False, None

        print("\n[+] Step 1: Running ETF Decomposition check...")
        decomp_chat = recipient._get_chats_to_run([chat_queue[0]], recipient, messages, sender, config)
        res_decomp = initiate_chats(decomp_chat)
        decomp_summary = res_decomp[0].summary
        
        decomp_data = extract_json_array(decomp_summary)
        
        all_articles = []
        is_etf = False
        constituents = []
        
        if isinstance(decomp_data, dict) and not decomp_data.get("error_flag", True) and decomp_data.get("constituents"):
            candidate_constituents = decomp_data["constituents"]
            if len(candidate_constituents) == 1 and candidate_constituents[0].get("ticker", "").upper() == ticker.upper():
                print(f"[*] Decomposition returned target ticker {ticker} only. Treating as single stock fallback.")
                is_etf = False
            elif len(candidate_constituents) > 0:
                constituents = candidate_constituents[:holdings]
                is_etf = True

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

        # Send the decomposition report/status to the nesting agent's conversation history
        if is_etf and constituents:
            decomp_report = (
                f"ETF Decomposition Report:\n"
                f"{json.dumps(decomp_data, indent=2)}"
            )
        else:
            decomp_report = (
                f"ETF Decomposition Report: This asset is a single stock. No constituents found."
            )
            
        recipient.send(
            message=decomp_report,
            recipient=sender,
            request_reply=False,
            silent=True
        )

        if not all_articles:
            recipient.send(
                message="[]",
                recipient=sender,
                request_reply=False,
                silent=True
            )
            return False, None

        # Batch score the articles in cycles of 5
        batch_size = 5
        batch_results = []
        
        for i in range(0, len(all_articles), batch_size):
            batch = all_articles[i:i + batch_size]
            print(f"[*] Batching scoring pipeline: processing articles {i+1} to {min(i+batch_size, len(all_articles))} of {len(all_articles)}")
            
            temp_chat_config = chat_queue[1].copy()
            temp_chat_config["message"] = (
                "Please score the following articles according to your instructions:\n\n"
                f"{json.dumps(batch, indent=2)}\n\n"
                "Respond with the list of scored articles."
            )
            
            scorer_chat = recipient._get_chats_to_run([temp_chat_config], recipient, messages, sender, config)
            res_scorer = initiate_chats(scorer_chat)
            
            summary_content = res_scorer[-1].summary
            scored_data = extract_json_array(summary_content)
            if scored_data is not None:
                batch_results.append(scored_data)
            else:
                try:
                    clean_content = summary_content
                    if clean_content.endswith("TERMINATE"):
                        clean_content = clean_content[:-9].strip()
                    batch_results.append(json.loads(clean_content))
                except Exception:
                    pass

        # Merge results and send back to CIO history
        from functions.tools.custom_reply import merge_scored_results
        merged_result = merge_scored_results(batch_results)
        scorer_summary = json.dumps(merged_result, indent=2)
        
        recipient.send(
            message=scorer_summary,
            recipient=sender,
            request_reply=False,
            silent=True
        )
        
        return False, None

    nested_chats = [
        {
            "recipient": decomp_agent,
            "message": lambda recipient, messages, sender, config: (
                f"Decompose the ETF tracker: {ticker}"
            ),
            "summary_method": "last_msg",
            "max_turns": 1,
        },
        {
            "recipient": scorer_agent,
            "message": lambda recipient, messages, sender, config: (
                "Please score the articles. Respond with the list of scored articles."
            ),
            "summary_method": "last_msg",
            "max_turns": 1,
        }
    ]
    
    cio_agent.register_nested_chats(
        nested_chats,
        trigger=user_proxy,
        reply_func_from_nested_chats=news_sentiment_custom_reply
    )

    # 7. Execute Agent-to-Agent conversation
    user_proxy.initiate_chat(
        cio_agent,
        message=f"Analyze the sentiment for ticker: {ticker}"
    )

    # 9. Clean response and output payload
    final_report_msg = extract_and_clean_response(user_proxy, cio_agent, is_json=True)
    
    try:
        return json.loads(final_report_msg)
    except json.JSONDecodeError as e:
        return {
            "ticker": ticker,
            "error": "Failed to parse CIO agent response as JSON.",
            "details": str(e),
            "raw_output": final_report_msg
        }


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
    
    print(f"Starting sentiment analysis for {args.ticker} (Limit: {args.limit}, Holdings: {args.holdings})...")
    
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

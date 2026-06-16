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
    from functions.tools.prepare_articles import prepare_articles
    from functions.agents import create_scorer_agent, create_cio_agent
    from functions.tools.custom_reply import custom_nested_chat_reply
    from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
    from autogen import UserProxyAgent
except ImportError as e:
    print(f"Error importing required sentiment modules: {e}", file=sys.stderr)
    print("Ensure you have activated your virtual environment and installed the dependencies.", file=sys.stderr)
    sys.exit(1)


def run_sentiment_analysis(
    ticker: str,
    limit: int = 5,
    csv_path: str = None,
    env_path: str = None
) -> dict:
    """
    Orchestrates the two-agent sentiment analysis workflow for a given ticker.
    
    This function is designed to be easily imported and reused by external systems, 
    such as FastAPI endpoints or background task queue workers.
    
    Args:
        ticker: The stock ticker symbol (e.g., 'AAPL').
        limit: The number of top news articles to fetch and score.
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
        nvidia_base_model = os.getenv("NVIDIA_BASE_MODEL", "").strip('"\' ')
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
        max_consecutive_auto_reply=1,
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

    # 6. Fetch news articles and prepare calibration context
    df_news = fetch_aggregate_all_news(symbol=ticker, limit=100)
    if df_news.empty:
        raise ValueError(f"No news articles found for symbol '{ticker}'.")
        
    articles_to_analyze = prepare_articles(df_news, db, limit=limit)

    # 7. Configure nested chat delegation (CIO delegates scoring to Scorer)
    nested_chats = [
        {
            "recipient": scorer_agent,
            "message": lambda recipient, messages, sender, config: (
                "Please score the following articles according to your instructions:\n\n"
                f"{messages[-1]['content']}\n\n"
                "Respond with the list of scored articles."
            ),
            "summary_method": "last_msg",
            "max_turns": 1,
        }
    ]
    
    cio_agent.register_nested_chats(
        nested_chats,
        trigger=user_proxy,
        reply_func_from_nested_chats=custom_nested_chat_reply
    )

    # 8. Execute Agent-to-Agent conversation
    user_proxy.initiate_chat(
        cio_agent,
        message=f"Analyze the following scored articles for ticker {ticker}:\n\n" + json.dumps(articles_to_analyze, indent=2)
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
        "--env", "-e",
        type=str,
        default=None,
        help="Path to environment file (default: .env.local)."
    )
    
    args = parser.parse_args()
    
    print(f"Starting sentiment analysis for {args.ticker} (Limit: {args.limit})...")
    
    try:
        report = run_sentiment_analysis(
            ticker=args.ticker,
            limit=args.limit,
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

import os
import sys
import json
from autogen import register_function

# Add sentiment directory to lookup path if not already present
script_dir = os.path.dirname(os.path.abspath(__file__))
sentiment_dir = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
if sentiment_dir not in sys.path:
    sys.path.insert(0, sentiment_dir)

try:
    from functions.utils.common.read_and_clean import extract_and_clean_response
    from functions.utils.news.news_helpers import (
        setup_clients_and_embeddings, 
        fetch_and_decompose_holdings, 
        batch_score_articles, 
        execute_reading_workers, 
        validate_compliance_limits
    )
    from functions.tools.prepare_articles import assign_label
    from functions.agents import setup_sentiment_pipeline_agents
    from functions.utils.math.formulas import calculate_raw_sentiment, calculate_portfolio_sentiment, normalize_weights
    from functions.utils.logging.pipeline_logger import get_pipeline_logger
except ImportError as e:
    print(f"Error importing required sentiment modules in orchestrator: {e}", file=sys.stderr)
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
    Logs progress info to console and to logs/pipeline.log file.
    """
    logger = get_pipeline_logger()
    
    logger.info(f"Setting up clients, settings, and embeddings configuration (env: {env_path}, calibration: {csv_path})...")
    
    # 1. Setup clients, settings and embeddings
    db, llm_config, base_llm_config, kimi_llm_config, prompt_dir, schema_dir = setup_clients_and_embeddings(
        env_path=env_path,
        csv_path=csv_path
    )
    
    logger.info("Instantiating pipeline agents (Scorer, CIO, Textual Inertia, Analyst Tension, Thesis Scribe)...")

    # 2. Instantiate pipeline agents
    agents_dict = setup_sentiment_pipeline_agents(
        llm_config=llm_config,
        base_llm_config=base_llm_config,
        kimi_llm_config=kimi_llm_config,
        prompt_dir=prompt_dir,
        schema_dir=schema_dir
    )
    
    user_proxy = agents_dict["user_proxy"]
    scorer_agent = agents_dict["scorer_agent"]
    cio_agent = agents_dict["cio_agent"]
    textual_inertia_agent = agents_dict["textual_inertia_agent"]
    tension_extractor_agent = agents_dict["tension_extractor_agent"]
    scribe_agent = agents_dict["scribe_agent"]

    logger.info("Registering mathematical formulas and labelling tools directly to CIO Agent...")

    # 3. Register math tools directly to the CIO Agent (User_Proxy as executor)
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

    logger.info(f"Retrieving and decomposing holdings for ticker '{ticker}' (Limit: {limit}, Holdings depth: {holdings})...")

    # 4. ETF Decomposition & News Ingestion
    is_etf, constituents, decomp_data, all_articles = fetch_and_decompose_holdings(
        ticker=ticker,
        holdings=holdings,
        limit=limit,
        db=db
    )

    if not all_articles:
        logger.warning("No news articles collected. Returning empty report.")
        return {
            "ticker": ticker,
            "error": "No news articles collected.",
            "metrics": {
                "sentiment_score": 0.0,
                "label": "Neutral"
            }
        }

    logger.info(f"Batch scoring {len(all_articles)} articles in cycles of 5 using Scorer Agent...")

    # 5. Batch scoring using Scorer Agent
    merged_result, scorer_summary = batch_score_articles(
        all_articles=all_articles,
        scorer_agent=scorer_agent,
        user_proxy=user_proxy
    )

    logger.info(f"Executing unstructured reading workers (SEC 10-K Textual Inertia & Call Transcript Tension) for {ticker}...")

    # 6. Run Unstructured Reading Workers Layer
    tickers_to_query = [c["ticker"] for c in constituents] if is_etf else [ticker]
    indicators_report_data = execute_reading_workers(
        tickers_to_query=tickers_to_query,
        user_proxy=user_proxy,
        textual_inertia_agent=textual_inertia_agent,
        tension_extractor_agent=tension_extractor_agent
    )

    # Format the indicators context
    indicators_report_str = "--- QUALITATIVE INDICATORS (TEXTUAL INERTIA & TENSION) ---\n"
    for t_symbol, data in indicators_report_data.items():
        indicators_report_str += (
            f"Asset: {t_symbol}\n"
            f"  - Textual Inertia (Lazy Prices) Score: {data['textual_inertia']} ({data['textual_inertia_reason']})\n"
            f"  - Analyst Q&A Tension Score: {data['tension']} ({data['tension_reason']})\n\n"
        )

    # 7. Inject direct context and run Consolidated Senior Analyst (CIO) Chat
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

    logger.info("Initiating Consolidated Senior Analyst (CIO) Chat...")
    user_proxy.initiate_chat(
        cio_agent,
        message=combined_message,
        clear_history=True
    )

    # 8. Extract and clean final report
    final_report_msg = extract_and_clean_response(user_proxy, cio_agent, is_json=True)
    
    try:
        final_report = json.loads(final_report_msg)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse CIO agent response as JSON: {e}")
        final_report = {
            "ticker": ticker,
            "error": "Failed to parse CIO agent response as JSON.",
            "details": str(e),
            "raw_output": final_report_msg
        }
        return final_report

    logger.info("Running compliance limits validation and Scribe manual override narrative checks...")

    # 9. Validate compliance limits and trigger override justification
    final_report = validate_compliance_limits(
        ticker=ticker,
        is_etf=is_etf,
        constituents=constituents,
        final_report=final_report,
        merged_result=merged_result,
        indicators_report_data=indicators_report_data,
        scribe_agent=scribe_agent,
        user_proxy=user_proxy
    )

    logger.info("Sentiment analysis pipeline execution complete.")
    return final_report

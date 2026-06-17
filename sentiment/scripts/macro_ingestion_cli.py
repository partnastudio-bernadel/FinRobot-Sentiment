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

# Import required modular dependencies
try:
    import autogen
    from autogen import UserProxyAgent, register_function
    from functions.tools.mcp_tools import (
        get_forexfactory_economic_calendar,
        get_alpha_vantage_historical_std,
        set_scheduler,
        set_calibration_agent
    )
    from functions.utils.formulas import calculate_macro_surprise
    from functions.utils.read_and_clean import (
        strip_name_hook,
        extract_and_clean_response
    )
    from functions.utils.scheduler import MacroScheduler
    from functions.utils.calibration_agent import MacroSurpriseCalibrationAgent
    from functions.utils.audit_logger import log_scheduler_event, extract_scheduler_block
    from functions import create_macro_cio_agent
    from functions.utils.config import generate_config
except ImportError as e:
    print(f"Error importing required macro ingestion modules: {e}", file=sys.stderr)
    print("Ensure you have activated your virtual environment and installed all dependencies.", file=sys.stderr)
    sys.exit(1)


def run_macro_ingestion_single(
    event_name: str,
    indicator_name: str,
    env_path: str = None
) -> dict:
    """
    Orchestrates the single-agent direct tool-calling macro ingestion workflow.
    """
    # 1. Resolve paths
    if env_path is None:
        env_path = os.path.join(sentiment_dir, ".env.local")
        if not os.path.exists(env_path):
            env_path = os.path.join(sentiment_dir, ".env")
            
    prompt_dir = os.path.join(sentiment_dir, "prompts")
    schema_dir = os.path.join(sentiment_dir, "schema_json")

    # Verify that paths exist
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Configuration file not found at: {env_path}")

    # 2. Load environment variables (with override=True)
    load_dotenv(env_path, override=True)

    # 3. Setup LLM configurations
    nvidia_tooling_model = os.getenv("NVIDIA_TOOLING_MODEL", "meta/llama-3.1-8b-instruct").strip('"\'  ')
    nvidia_api_endpoint = os.getenv("NVIDIA_API_ENDPOINT", "https://integrate.api.nvidia.com/v1").strip('"\'  ')
    nvidia_api_key = os.getenv("NVIDIA_API_KEY", "").strip('"\'  ')
    
    if not nvidia_api_key:
        raise ValueError("NVIDIA_API_KEY is not configured in the loaded environment variables.")

    # In mcp_helper, read SCRAPER_TIMEOUT_MS if it exists to align timeouts
    env_timeout = os.getenv("SCRAPER_TIMEOUT_MS")
    if env_timeout:
        try:
            import functions.utils.mcp_helper as mh
            mh._MCP_TIMEOUT = float(env_timeout) / 1000.0
            print(f"[*] Dynamically set client MCP timeout to {mh._MCP_TIMEOUT}s from environment.")
        except Exception as e:
            print(f"[!] Warning: failed to dynamically set client MCP timeout: {e}")

    config_list = generate_config(nvidia_tooling_model, nvidia_api_endpoint, nvidia_api_key)
    tooling_llm_config = {"config_list": config_list, "model": nvidia_tooling_model}

    # 3b. Instantiate Smart Scheduler and Calibration Agent, inject into mcp_tools
    scheduler = MacroScheduler()
    calibration_agent = MacroSurpriseCalibrationAgent()
    set_scheduler(scheduler)
    set_calibration_agent(calibration_agent)
    scheduler.reset()  # Ensure clean state before this pipeline run

    # 4. Instantiate Chief Macro Economist (pointing to our single-agent prompt file)
    macro_cio_agent = create_macro_cio_agent(
        os.path.join(prompt_dir, "chief_macro_economist_prompt.txt"),
        os.path.join(schema_dir, "macro_cio_schema.json"),
        os.path.join(schema_dir, "macro_cio_example.json"),
        tooling_llm_config
    )

    user_proxy = UserProxyAgent(
        name="User_Proxy",
        human_input_mode="NEVER",
        is_termination_msg=lambda x: x.get("content", "") and "TERMINATE" in x.get("content", ""),
        max_consecutive_auto_reply=15,  # Give enough turns for direct tool calling cycles
        code_execution_config={"use_docker": False}
    )

    # Register strip_name_hook to address strict NIM payload parameters
    for agent in [user_proxy, macro_cio_agent]:
        agent.register_hook(
            hookable_method="process_all_messages_before_reply",
            hook=strip_name_hook
        )

    # 5. Register Python functions as AutoGen tool calls directly to the Chief Economist
    # In this single agent design, Chief Economist proposes and User Proxy executes.
    register_function(
        get_forexfactory_economic_calendar,
        caller=macro_cio_agent,
        executor=user_proxy,
        name="get_forexfactory_economic_calendar",
        description="Retrieves economic calendar events from ForexFactory for a specified period."
    )

    register_function(
        get_alpha_vantage_historical_std,
        caller=macro_cio_agent,
        executor=user_proxy,
        name="get_alpha_vantage_historical_std",
        description="Retrieves rolling historical standard deviation of a macroeconomic indicator from Alpha Vantage."
    )

    register_function(
        calculate_macro_surprise,
        caller=macro_cio_agent,
        executor=user_proxy,
        name="calculate_macro_surprise",
        description="Computes macroeconomic surprise metrics."
    )

    # 6. Execute Chat
    print(f"\n[+] Initiating Single-Agent Macro Ingestion workflow for event: '{event_name}'...")
    user_proxy.initiate_chat(
        macro_cio_agent,
        message=(
            f"Retrieve economic details for the USD '{event_name}' event and the historical standard deviation for '{indicator_name}'. "
            "Aggregate them to calculate the macro surprise index S_t and output the final JSON report."
        )
    )

    # 7. Extract & clean JSON payload
    final_macro_report = extract_and_clean_response(user_proxy, macro_cio_agent, is_json=True)
    
    try:
        parsed = json.loads(final_macro_report)
    except json.JSONDecodeError as e:
        return {
            "event_name": event_name,
            "indicator_name": indicator_name,
            "error": "Failed to parse Chief Economist response as JSON.",
            "details": str(e),
            "raw_output": final_macro_report
        }

    # 8. Strip _scheduler audit block (if present) and route to audit logger
    parsed, scheduler_meta = extract_scheduler_block(parsed)
    if scheduler_meta:
        scheduler_meta["event_name"] = event_name
        log_scheduler_event(scheduler_meta)

    return parsed


def main():
    parser = argparse.ArgumentParser(
        description="CLI utility for running the Single-Agent Macro Ingestion pipeline."
    )
    parser.add_argument(
        "--event", "-v",
        type=str,
        default="CPI m/m",
        help="Target economic calendar event name to harvest (default: 'CPI m/m')."
    )
    parser.add_argument(
        "--indicator", "-i",
        type=str,
        default="CPI",
        help="Baseline macro indicator to calculate rolling standard deviation for (default: 'CPI')."
    )
    parser.add_argument(
        "--env", "-e",
        type=str,
        default=None,
        help="Path to environment configuration file (default: .env.local)."
    )
    
    args = parser.parse_args()
    
    print(f"Starting single-agent macro surprise calculation for '{args.event}' using indicator '{args.indicator}'...")
    
    try:
        report = run_macro_ingestion_single(
            event_name=args.event,
            indicator_name=args.indicator,
            env_path=args.env
        )
        print("\n================ MACRO INGESTION SURPRISE REPORT ================")
        print(json.dumps(report, indent=2))
    except Exception as e:
        print(f"\n[Error] Failed to complete macro calculations: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

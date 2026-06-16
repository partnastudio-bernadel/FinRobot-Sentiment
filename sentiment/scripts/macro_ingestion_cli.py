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
    from autogen import UserProxyAgent, register_function, initiate_chats
    from functions.utils.mcp_helper import (
        run_async_in_thread,
        async_query_alpha_vantage_mcp,
        async_query_forexfactory_mcp
    )
    from functions.tools.mcp_tools import (
        get_forexfactory_economic_calendar,
        get_alpha_vantage_historical_std
    )
    from functions.utils.formulas import calculate_macro_surprise
    from functions.utils.read_and_clean import (
        strip_name_hook,
        extract_and_clean_response
    )
    from functions import (
        create_forexfactory_agent,
        create_alphavantage_agent,
        create_macro_cio_agent
    )
    from functions.utils.config import generate_config
except ImportError as e:
    print(f"Error importing required macro ingestion modules: {e}", file=sys.stderr)
    print("Ensure you have activated your virtual environment and installed all dependencies.", file=sys.stderr)
    sys.exit(1)


def run_macro_ingestion(
    event_name: str,
    indicator_name: str,
    env_path: str = None
) -> dict:
    """
    Orchestrates the multi-agent macro ingestion and surprise score calculation workflow.
    
    This function is designed to be easily imported and integrated by external controllers,
    such as FastAPI routes, message queues, or cron scripts.
    
    Args:
        event_name: The target economic event name (e.g. 'CPI m/m').
        indicator_name: The baseline macro indicator name (e.g. 'CPI').
        env_path: Optional path to the env file containing API keys and endpoints.
        
    Returns:
        A dictionary representing the final calculated surprise report.
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
    # Re-generate configs dynamically based on the custom env loaded above
    nvidia_base_model = os.getenv("NVIDIA_BASE_MODEL", "").strip('"\' ')
    nvidia_tooling_model = os.getenv("NVIDIA_TOOLING_MODEL", "meta/llama-3.1-8b-instruct").strip('"\' ')
    nvidia_api_endpoint = os.getenv("NVIDIA_API_ENDPOINT", "https://integrate.api.nvidia.com/v1").strip('"\' ')
    nvidia_api_key = os.getenv("NVIDIA_API_KEY", "").strip('"\' ')
    
    if not nvidia_api_key:
        raise ValueError("NVIDIA_API_KEY is not configured in the loaded environment variables.")

    config_list = generate_config(nvidia_tooling_model, nvidia_api_endpoint, nvidia_api_key)
    base_config_list = generate_config(nvidia_base_model, nvidia_api_endpoint, nvidia_api_key)
    
    tooling_llm_config = {"config_list": config_list, "model": nvidia_tooling_model}
    base_llm_config = {"config_list": base_config_list, "model": nvidia_base_model}

    # 4. Instantiate sub-agents and orchestrator
    forexfactory_agent = create_forexfactory_agent(
        os.path.join(prompt_dir, "forexfactory_scraper_prompt.txt"),
        os.path.join(schema_dir, "forexfactory_schema.json"),
        os.path.join(schema_dir, "forexfactory_example.json"),
        tooling_llm_config
    )

    alphavantage_agent = create_alphavantage_agent(
        os.path.join(prompt_dir, "alphavantage_agent_prompt.txt"),
        os.path.join(schema_dir, "alphavantage_schema.json"),
        os.path.join(schema_dir, "alphavantage_example.json"),
        tooling_llm_config
    )

    macro_cio_agent = create_macro_cio_agent(
        os.path.join(prompt_dir, "chief_macro_economist_prompt.txt"),
        os.path.join(schema_dir, "macro_cio_schema.json"),
        os.path.join(schema_dir, "macro_cio_example.json"),
        base_llm_config
    )

    user_proxy = UserProxyAgent(
        name="User_Proxy",
        human_input_mode="NEVER",
        is_termination_msg=lambda x: x.get("content", "") and "TERMINATE" in x.get("content", ""),
        max_consecutive_auto_reply=1,
        code_execution_config={"use_docker": False}
    )

    # Register strip_name_hook to address strict NIM payload parameters
    for agent in [user_proxy, forexfactory_agent, alphavantage_agent, macro_cio_agent]:
        agent.register_hook(
            hookable_method="process_all_messages_before_reply",
            hook=strip_name_hook
        )

    # 5. Register Python functions as AutoGen tool calls
    register_function(
        get_forexfactory_economic_calendar,
        caller=forexfactory_agent,
        executor=macro_cio_agent,
        name="get_forexfactory_economic_calendar",
        description="Retrieves economic calendar events from ForexFactory for a specified period."
    )

    register_function(
        get_alpha_vantage_historical_std,
        caller=alphavantage_agent,
        executor=macro_cio_agent,
        name="get_alpha_vantage_historical_std",
        description="Retrieves rolling historical standard deviation of a macroeconomic indicator from Alpha Vantage."
    )

    # 6. Configure custom nested chat reply handler to resolve AutoGen swallowing bugs
    def custom_macro_nested_chat_reply(chat_queue, recipient, messages, sender, config):
        chats_to_run = recipient._get_chats_to_run(chat_queue, recipient, messages, sender, config)
        if not chats_to_run:
            return True, None
            
        print(f"\n[+] Running nested delegation chats sequentially...")
        res = initiate_chats(chats_to_run)
        
        # Extract the results from sub-agents
        forexfactory_summary = res[0].summary
        if not forexfactory_summary or not forexfactory_summary.strip():
            for msg in reversed(res[0].chat_history):
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    forexfactory_summary = content.strip()
                    break

        alphavantage_summary = res[1].summary
        if not alphavantage_summary or not alphavantage_summary.strip():
            for msg in reversed(res[1].chat_history):
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    alphavantage_summary = content.strip()
                    break
        
        combined_summary = (
            f"Economic Calendar Events Data:\n{forexfactory_summary}\n\n"
            f"Historical Standard Deviation Data:\n{alphavantage_summary}"
        )
        
        print("\n[+] Injecting combined nested chat results back to the Chief Economist:")
        print(combined_summary)
        
        # Send direction corrected (User_Proxy -> Chief_Macro_Economist) so 70B treats it as incoming input
        sender.send(
            message=combined_summary,
            recipient=recipient,
            request_reply=False,
            silent=True
        )
        
        return False, None

    # Define delegation chats
    nested_chats = [
        {
            "recipient": forexfactory_agent,
            "message": lambda recipient, messages, sender, config: (
                f"Please retrieve the economic calendar events for this month to find the USD '{event_name}' details."
            ),
            "summary_method": "last_msg",
            "max_turns": 2,
        },
        {
            "recipient": alphavantage_agent,
            "message": lambda recipient, messages, sender, config: (
                f"Please compute and return the rolling historical standard deviation for macro indicator '{indicator_name}' (window 12)."
            ),
            "summary_method": "last_msg",
            "max_turns": 2,
        }
    ]

    macro_cio_agent.register_nested_chats(
        nested_chats,
        trigger=user_proxy,
        reply_func_from_nested_chats=custom_macro_nested_chat_reply
    )

    # 7. Execute Chat
    print(f"\n[+] Initiating Macro Ingestion delegation workflow for event: '{event_name}'...")
    user_proxy.initiate_chat(
        macro_cio_agent,
        message=(
            f"Retrieve economic details for the USD '{event_name}' event and the historical standard deviation for '{indicator_name}'. "
            "Aggregate them to calculate the macro surprise index S_t and output the final JSON report."
        )
    )

    # 8. Extract & clean JSON payload
    final_macro_report = extract_and_clean_response(user_proxy, macro_cio_agent, is_json=True)
    
    try:
        return json.loads(final_macro_report)
    except json.JSONDecodeError as e:
        return {
            "event_name": event_name,
            "indicator_name": indicator_name,
            "error": "Failed to parse Chief Economist response as JSON.",
            "details": str(e),
            "raw_output": final_macro_report
        }


def main():
    parser = argparse.ArgumentParser(
        description="CLI utility for running the Multi-Agent Macro Ingestion & Surprise score pipeline."
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
    
    print(f"Starting macro surprise calculation for '{args.event}' using indicator '{args.indicator}'...")
    
    try:
        report = run_macro_ingestion(
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

import sys
import os
import json
import asyncio
import pandas as pd
import numpy as np
import requests
from dotenv import load_dotenv

# Ensure the sentiment folder is in python path for importing modules
notebook_dir = os.getcwd()
sentiment_dir = os.path.dirname(notebook_dir)
if sentiment_dir not in sys.path:
    sys.path.insert(0, sentiment_dir)

# Load environment variables from .env.local
load_dotenv("../.env.local", override=True)


# --------------------------------------------------------------------------------

import autogen

from autogen import (
    UserProxyAgent, 
    register_function,
    initiate_chats
)

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
    llm_config,
    base_llm_config,
    tooling_llm_config,
    create_forexfactory_agent,
    create_alphavantage_agent,
    create_macro_cio_agent
)

# --------------------------------------------------------------------------------


# Create the sub-agents and orchestrator using FinRobot class
forexfactory_agent = create_forexfactory_agent(
    "../prompts/forexfactory_scraper_prompt.txt",
    "../schema_json/forexfactory_schema.json",
    "../schema_json/forexfactory_example.json",
    tooling_llm_config
)

alphavantage_agent = create_alphavantage_agent(
    "../prompts/alphavantage_agent_prompt.txt",
    "../schema_json/alphavantage_schema.json",
    "../schema_json/alphavantage_example.json",
    tooling_llm_config
)

macro_cio_agent = create_macro_cio_agent(
    "../prompts/chief_macro_economist_prompt.txt",
    "../schema_json/macro_cio_schema.json",
    "../schema_json/macro_cio_example.json",
    base_llm_config
)

# Create the UserProxy
user_proxy = UserProxyAgent(
    name="User_Proxy",
    human_input_mode="NEVER",
    is_termination_msg=lambda x: x.get("content", "") and "TERMINATE" in x.get("content", ""),
    max_consecutive_auto_reply=1,
    code_execution_config={"use_docker": False}
)

# Hook to strip 'name' parameter from message payloads to satisfy strict client API constraints (e.g. NVIDIA NIM)
for agent in [user_proxy, forexfactory_agent, alphavantage_agent, macro_cio_agent]:
    agent.register_hook(
        hookable_method="process_all_messages_before_reply",
        hook=strip_name_hook
    )


# --------------------------------------------------------------------------------

# Register tools to the respective agents for AutoGen tool-calling

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


# --------------------------------------------------------------------------------


# Set up the economic calendar event we want to analyze
target_event = "CPI m/m"
target_indicator = "CPI"

# Define a custom nested chat reply function to avoid the orchestrator's response being swallowed
def custom_macro_nested_chat_reply(chat_queue, recipient, messages, sender, config):
    chats_to_run = recipient._get_chats_to_run(chat_queue, recipient, messages, sender, config)
    if not chats_to_run:
        return True, None
        
    print(f"\n[+] Running nested delegation chats sequentially...")
    res = initiate_chats(chats_to_run)
    
    # Combine the summaries from the sub-agents
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
    
    # Send the combined results silently to the sender (User_Proxy) to insert into the chat history
    sender.send(
        message=combined_summary,
        recipient=recipient,
        request_reply=False,
        silent=True
    )
    
    # Return (False, None) to trigger the Chief Economist's own LLM aggregation/reply generation step
    return False, None

# Configure nested chats on the Macro CIO agent
nested_chats = [
    {
        "recipient": forexfactory_agent,
        "message": lambda recipient, messages, sender, config: (
            f"Please retrieve the economic calendar events for this month to find the USD '{target_event}' details."
        ),
        "summary_method": "last_msg",
        "max_turns": 2,
    },
    {
        "recipient": alphavantage_agent,
        "message": lambda recipient, messages, sender, config: (
            f"Please compute and return the rolling historical standard deviation for macro indicator '{target_indicator}' (window 12)."
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

print(f"\n[+] Initiating Macro Ingestion delegation workflow for event: '{target_event}'...")
user_proxy.initiate_chat(
    macro_cio_agent,
    message=(
        f"Retrieve economic details for the USD '{target_event}' event and the historical standard deviation for '{target_indicator}'. "
        "Aggregate them to calculate the macro surprise index S_t and output the final JSON report."
    )
)

final_macro_report = extract_and_clean_response(user_proxy, macro_cio_agent, is_json=True)
print("\n================ FINAL MACRO SURPRISE REPORT ================")
print(final_macro_report)

# --------------------------------------------------------------------------------


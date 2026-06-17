import os
import numpy as np
from functions.utils.mcp_helper import (
    run_async_in_thread,
    async_query_forexfactory_mcp,
    async_query_alpha_vantage_mcp
)
from functions.utils.scheduler import MacroScheduler
from functions.utils.calibration_agent import MacroSurpriseCalibrationAgent

# ---------------------------------------------------------------------------
# Module-level singletons
#
# These are used when mcp_tools functions are called directly (e.g. during
# AutoGen nested chat sub-agent execution). The macro_ingestion_cli.py will
# inject its own pre-configured instances via set_scheduler() / set_calibration_agent()
# for full telemetry and fallback tracking across the pipeline run.
# ---------------------------------------------------------------------------
_scheduler: MacroScheduler = MacroScheduler()
_calibration_agent: MacroSurpriseCalibrationAgent = MacroSurpriseCalibrationAgent()


def set_scheduler(scheduler: MacroScheduler) -> None:
    """Inject a pre-configured MacroScheduler instance from the CLI entry point."""
    global _scheduler
    _scheduler = scheduler


def set_calibration_agent(agent: MacroSurpriseCalibrationAgent) -> None:
    """Inject a pre-configured MacroSurpriseCalibrationAgent from the CLI entry point."""
    global _calibration_agent
    _calibration_agent = agent


def get_scheduler() -> MacroScheduler:
    """Returns the active MacroScheduler instance."""
    return _scheduler


def get_calibration_agent() -> MacroSurpriseCalibrationAgent:
    """Returns the active MacroSurpriseCalibrationAgent instance."""
    return _calibration_agent


# ---------------------------------------------------------------------------
# ForexFactory Tool
# ---------------------------------------------------------------------------

def get_forexfactory_economic_calendar(time_period: str = "this_month", event_filter: str = None, currency_filter: str = None) -> list:
    """Retrieves economic calendar events from ForexFactory for a specified period using ForexFactory MCP.
    
    Args:
        time_period (str, optional): The calendar query window (e.g., 'today', 'tomorrow', 'this_week', 'this_month'). Defaults to 'this_month'.
        event_filter (str, optional): An optional event name filter (e.g. 'CPI m/m') to retrieve only specific events and avoid context truncation. Defaults to None.
        currency_filter (str, optional): An optional currency filter (e.g. 'USD', 'EUR') to filter events by currency name. Defaults to None.
        
    Returns:
        list: A list of dicts representing economic events.
    """
    print(f"[*] Fetching economic calendar events for time period: {time_period} via ForexFactory MCP...")

    try:
        mcp_result = _scheduler.execute_with_guard(
            async_query_forexfactory_mcp,
            "ffcal_get_calendar_events", {"time_period": time_period},
            source="forexfactory"
        )
    except RuntimeError as e:
        # Scheduler has already updated state; caller uses build_fallback_payload()
        raise RuntimeError(str(e)) from e

    if isinstance(mcp_result, dict) and mcp_result.get("status") == "error":
        raise RuntimeError(f"ForexFactory MCP tool failed: {mcp_result.get('error_msg')}")

    if isinstance(mcp_result, list):
        filtered_results = mcp_result
        if event_filter:
            filter_lower = event_filter.strip().lower()
            filtered_results = [
                e for e in filtered_results
                if filter_lower in str(e.get("title") or "").strip().lower()
            ]
        if currency_filter:
            curr_lower = currency_filter.strip().lower()
            filtered_results = [
                e for e in filtered_results
                if curr_lower == str(e.get("currency") or "").strip().lower()
            ]
        print(f"[*] Filtered events matching filter='{event_filter}', currency='{currency_filter}': {len(filtered_results)} of {len(mcp_result)} events")
        return filtered_results

    return mcp_result


# ---------------------------------------------------------------------------
# Alpha Vantage Historical Std Tool
# ---------------------------------------------------------------------------

def get_alpha_vantage_historical_std(indicator: str, window: int = 12) -> float:
    """Retrieves the rolling historical standard deviation of a macroeconomic indicator from Alpha Vantage via MCP.
    
    Routed through MacroSurpriseCalibrationAgent for retry logic, in-memory
    caching, and type coercion fallback (returns 1.0 with warning if live data
    is unavailable), ensuring a guaranteed float always reaches formulas.py.

    Args:
        indicator (str): The indicator name matching Alpha Vantage keys (e.g., 'CPI', 'UNEMPLOYMENT', 'RETAIL_SALES').
        window (int, optional): The rolling historical window of months/releases to compute standard deviation over. Defaults to 12.
        
    Returns:
        float: The rolling historical standard deviation of the indicator values.
    """
    window = int(window)
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip('"')
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY is not configured in environment.")

    print(f"[*] Fetching historical baseline for indicator: {indicator} (Rolling window: {window} periods) via Alpha Vantage MCP...")

    std_val, warning_flag = _calibration_agent.get_historical_std(
        indicator=indicator,
        window=window,
        api_key=api_key
    )

    if warning_flag:
        print(f"[!] Calibration fallback used for '{indicator}': std = {std_val} (warning_flag=True)")
    else:
        print(f"[*] Historical std for '{indicator}': {std_val}")

    return std_val

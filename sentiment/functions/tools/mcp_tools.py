import os
import numpy as np
from functions.utils.mcp_helper import (
    run_async_in_thread,
    async_query_forexfactory_mcp,
    async_query_alpha_vantage_mcp
)

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
    
    mcp_result = run_async_in_thread(
        async_query_forexfactory_mcp("ffcal_get_calendar_events", {"time_period": time_period})
    )
        
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



def get_alpha_vantage_historical_std(indicator: str, window: int = 12) -> float:
    """Retrieves the rolling historical standard deviation of a macroeconomic indicator from Alpha Vantage via MCP.
    
    Args:
        indicator (str): The indicator name matching Alpha Vantage keys (e.g., 'CPI', 'UNEMPLOYMENT', 'RETAIL_SALES').
        window (int, optional): The rolling historical window of months/releases to compute standard deviation over. Defaults to 12.
        
    Returns:
        float: The rolling historical standard deviation of the indicator values.
    """
    window = int(window)
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip('"' )
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY is not configured in environment.")
        
    print(f"[*] Fetching historical baseline for indicator: {indicator} (Rolling window: {window} periods) via Alpha Vantage MCP...")
    
    mcp_result = run_async_in_thread(
        async_query_alpha_vantage_mcp(
            tool_name=indicator.upper(),
            arguments={},
            api_key=api_key
        )
    )
    
    if isinstance(mcp_result, dict) and mcp_result.get("status") == "error":
        raise RuntimeError(f"Alpha Vantage MCP tool failed: {mcp_result.get('error_msg')}")
        
    records = mcp_result.get("data", []) if isinstance(mcp_result, dict) else []
    if not records:
        if isinstance(mcp_result, dict) and "Information" in mcp_result:
            print(f"[!] Alpha Vantage rate limit reached: {mcp_result['Information']}")
            fallbacks = {
                "CPI": 1.1410887363094182,
                "UNEMPLOYMENT": 0.2,
                "RETAIL_SALES": 0.8
            }
            fallback_val = fallbacks.get(indicator.upper(), 1.0)
            print(f"[!] Using fallback historical standard deviation: {fallback_val}")
            return fallback_val
        raise ValueError(f"No historical records returned for indicator: {indicator}. MCP response: {mcp_result}")
        
    # Extract values as floats and compute MoM differences
    values = []
    for record in records[:window+1]:
        val_str = record.get("value", "")
        if val_str and val_str != ".":
            values.append(float(val_str))
            
    if len(values) < 2:
        raise ValueError(f"Insufficient historical data points ({len(values)}) to compute standard deviation.")
        
    # Calculate changes/surprises
    changes = np.diff(values)
    std_val = float(np.std(changes))
    
    if std_val == 0.0:
        raise ValueError("Computed standard deviation is zero; cannot divide by zero.")
        
    return std_val

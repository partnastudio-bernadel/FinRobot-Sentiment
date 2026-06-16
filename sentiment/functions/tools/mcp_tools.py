import os
import numpy as np
from functions.utils.mcp_helper import (
    run_async_in_thread,
    async_query_forexfactory_mcp,
    async_query_alpha_vantage_mcp
)

def get_forexfactory_economic_calendar(time_period: str = "this_month") -> list:
    """Retrieves economic calendar events from ForexFactory for a specified period using ForexFactory MCP.
    
    Args:
        time_period (str, optional): The calendar query window (e.g., 'today', 'tomorrow', 'this_week', 'this_month'). Defaults to 'this_month'.
        
    Returns:
        list: A list of dicts representing economic events.
    """
    print(f"[*] Fetching economic calendar events for time period: {time_period} via ForexFactory MCP...")
    
    mcp_result = run_async_in_thread(
        async_query_forexfactory_mcp("ffcal_get_calendar_events", {"time_period": time_period})
    )
        
    if isinstance(mcp_result, dict) and mcp_result.get("status") == "error":
        raise RuntimeError(f"ForexFactory MCP tool failed: {mcp_result.get('error_msg')}")
        
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
        
    records = mcp_result.get("data", [])
    if not records:
        raise ValueError(f"No historical records returned for indicator: {indicator}")
        
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

import time
from datetime import datetime, timezone
from typing import Optional, Tuple

from functions.utils.mcp_helper import run_async_in_thread, async_query_alpha_vantage_mcp
from functions.utils.scheduler import RateLimitError


class MacroSurpriseCalibrationAgent:
    """
    Dedicated calibration layer that owns the Alpha Vantage historical standard
    deviation fetch for the Macro Severity Surprise Index (S_t).

    Responsibilities:
      - In-memory TTL cache to absorb rate limit windows between runs.
      - Retry with exponential backoff (max 3 attempts on 429/timeout).
      - Type coercion fallback: returns (1.0, warning_flag=True) if Alpha Vantage
        returns None, 0.0, or an empty / rate-limited response.

    This ensures the MacroScheduler always receives a guaranteed float, never
    a raw exception or empty string, keeping the division-by-zero guard in
    formulas.calculate_macro_surprise as the last line of defence rather than
    the first.

    The default fallback values below are empirically computed rolling std devs
    used as conservative baselines when live data is unavailable.
    """

    # Conservative pre-computed fallback std devs (empirical baselines)
    FALLBACK_STD: dict = {
        "CPI": 1.1410887363094182,
        "UNEMPLOYMENT": 0.2,
        "RETAIL_SALES": 0.8,
        "NFP": 85.0,
        "GDP": 0.5,
    }

    # Default to 1.0 for any unknown indicator (prevents division by zero)
    DEFAULT_FALLBACK: float = 1.0

    def __init__(self, cache_ttl_seconds: int = 3600):
        """
        Args:
            cache_ttl_seconds: How long a cached std result is considered fresh.
                               Defaults to 1 hour. Set to 0 to disable caching.
        """
        self._cache: dict = {}  # {indicator_key: (std_value, fetched_at_epoch)}
        self._ttl: int = cache_ttl_seconds

    def get_historical_std(
        self,
        indicator: str,
        window: int = 12,
        api_key: str = "",
    ) -> Tuple[float, bool]:
        """
        Returns the rolling historical standard deviation for a macro indicator.

        Execution order:
          1. Cache hit check (within TTL window).
          2. Alpha Vantage MCP fetch with retry/backoff (max 3 attempts).
          3. Coercion fallback (indicator-specific or 1.0 generic).

        Args:
            indicator:  Indicator name matching Alpha Vantage keys (e.g. 'CPI').
            window:     Rolling window of releases to compute std dev over.
            api_key:    Alpha Vantage API key.

        Returns:
            Tuple[float, bool]: (historical_std, warning_flag)
                - warning_flag is True when a fallback value was used instead
                  of live Alpha Vantage data.
        """
        indicator_key = indicator.upper()

        # 1. Cache lookup
        cached = self._get_from_cache(indicator_key)
        if cached is not None:
            return cached, False

        # 2. Retry fetch
        std_val = self._fetch_with_retry(indicator_key, window, api_key, max_retries=3)

        if std_val is not None and std_val > 0.0:
            self._set_cache(indicator_key, std_val)
            return std_val, False

        # 3. Coercion fallback
        fallback = self.FALLBACK_STD.get(indicator_key, self.DEFAULT_FALLBACK)
        print(
            f"[CalibrationAgent] Coercion fallback applied for '{indicator_key}': "
            f"std = {fallback} (warning_flag=True)"
        )
        return fallback, True

    # ------------------------------------------------------------------
    # Cache Helpers
    # ------------------------------------------------------------------

    def _get_from_cache(self, key: str) -> Optional[float]:
        """Returns cached value if within TTL, else None."""
        if self._ttl <= 0:
            return None
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, fetched_at = entry
        if (time.monotonic() - fetched_at) < self._ttl:
            print(f"[CalibrationAgent] Cache hit for '{key}': std = {value}")
            return value
        # TTL expired — evict
        del self._cache[key]
        return None

    def _set_cache(self, key: str, value: float):
        """Stores a fresh value in the in-memory TTL cache."""
        self._cache[key] = (value, time.monotonic())

    def clear_cache(self):
        """Manually flushes all cached standard deviation values."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Retry Fetch
    # ------------------------------------------------------------------

    def _fetch_with_retry(
        self,
        indicator: str,
        window: int,
        api_key: str,
        max_retries: int = 3
    ) -> Optional[float]:
        """
        Attempts to fetch the rolling historical std from Alpha Vantage with
        exponential backoff (1s, 2s, 4s) on RateLimitError or timeout.

        Returns:
            float if successful, None if all attempts exhausted.
        """
        import numpy as np

        delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                mcp_result = run_async_in_thread(
                    async_query_alpha_vantage_mcp(
                        tool_name=indicator,
                        arguments={},
                        api_key=api_key
                    )
                )

                if isinstance(mcp_result, dict) and mcp_result.get("status") == "error":
                    print(f"[CalibrationAgent] MCP error on attempt {attempt}: {mcp_result.get('error_msg')}")
                    raise RateLimitError(mcp_result.get("error_msg", "MCP error"))

                # Rate limit response comes back as a dict with "Information" key
                if isinstance(mcp_result, dict) and "Information" in mcp_result:
                    print(f"[CalibrationAgent] Rate limit on attempt {attempt}: {mcp_result['Information']}")
                    raise RateLimitError(mcp_result["Information"])

                records = mcp_result.get("data", []) if isinstance(mcp_result, dict) else []
                if not records:
                    print(f"[CalibrationAgent] Empty data on attempt {attempt}.")
                    return None

                # Compute rolling std dev from MoM differences
                values = []
                for record in records[:window + 1]:
                    val_str = record.get("value", "")
                    if val_str and val_str != ".":
                        values.append(float(val_str))

                if len(values) < 2:
                    print(f"[CalibrationAgent] Insufficient data points ({len(values)}) on attempt {attempt}.")
                    return None

                std_val = float(np.std(np.diff(values)))
                if std_val > 0.0:
                    return std_val

                return None

            except RateLimitError:
                if attempt < max_retries:
                    print(f"[CalibrationAgent] Rate limit hit. Retrying in {delay}s (attempt {attempt}/{max_retries})...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    print(f"[CalibrationAgent] All {max_retries} retry attempts exhausted.")
                    return None

            except Exception as e:
                print(f"[CalibrationAgent] Unexpected error on attempt {attempt}: {e}")
                return None

        return None

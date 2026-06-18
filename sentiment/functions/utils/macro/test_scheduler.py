"""
Unit tests for MacroScheduler, MacroSurpriseCalibrationAgent, and audit_logger.

Run with:
    python -m pytest sentiment/functions/utils/test_scheduler.py -v
"""
import asyncio
import json
import os
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

# Ensure the sentiment directory is on the path
_sentinel_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _sentinel_dir not in sys.path:
    sys.path.insert(0, _sentinel_dir)

from functions.utils.macro.scheduler import MacroScheduler, RateLimitError, MCPConnectionError
from functions.utils.macro.calibration_agent import MacroSurpriseCalibrationAgent
from functions.utils.logging.audit_logger import extract_scheduler_block


# ---------------------------------------------------------------------------
# MacroScheduler Tests
# ---------------------------------------------------------------------------

class TestMacroScheduler(unittest.TestCase):

    def setUp(self):
        self.scheduler = MacroScheduler()

    def _make_coro(self, return_value=None, raise_exc=None):
        """Helper: returns a coroutine function that either returns or raises."""
        async def coro(*args, **kwargs):
            if raise_exc:
                raise raise_exc
            return return_value
        return coro

    # --- execute_with_guard: Success path ---

    def test_execute_success_sets_state_ok(self):
        fn = self._make_coro(return_value={"data": "ok"})
        result = self.scheduler.execute_with_guard(fn, source="test")
        self.assertEqual(self.scheduler.state, "OK")
        self.assertEqual(result, {"data": "ok"})
        self.assertFalse(self.scheduler.stale_calendar_flag)

    # --- execute_with_guard: TimeoutError → TIMEOUT ---

    def test_execute_timeout_sets_state_timeout(self):
        fn = self._make_coro(raise_exc=asyncio.TimeoutError())
        with self.assertRaises(RuntimeError):
            self.scheduler.execute_with_guard(fn, source="forexfactory")
        self.assertEqual(self.scheduler.state, "TIMEOUT")
        self.assertTrue(self.scheduler.stale_calendar_flag)

    # --- execute_with_guard: RateLimitError → RATE_LIMITED ---

    def test_execute_rate_limit_sets_state_rate_limited(self):
        fn = self._make_coro(raise_exc=RateLimitError("HTTP 429"))
        with self.assertRaises(RuntimeError):
            self.scheduler.execute_with_guard(fn, source="alpha_vantage")
        self.assertEqual(self.scheduler.state, "RATE_LIMITED")
        self.assertTrue(self.scheduler.stale_calendar_flag)

    # --- execute_with_guard: ConnectionError → STALE ---

    def test_execute_connection_error_sets_state_stale(self):
        fn = self._make_coro(raise_exc=ConnectionError("refused"))
        with self.assertRaises(RuntimeError):
            self.scheduler.execute_with_guard(fn, source="forexfactory")
        self.assertEqual(self.scheduler.state, "STALE")
        self.assertTrue(self.scheduler.stale_calendar_flag)

    # --- execute_with_guard: Unclassified → STALE ---

    def test_execute_unclassified_error_sets_state_stale(self):
        fn = self._make_coro(raise_exc=ValueError("unexpected"))
        with self.assertRaises(RuntimeError):
            self.scheduler.execute_with_guard(fn, source="alpha_vantage")
        self.assertEqual(self.scheduler.state, "STALE")

    # --- build_fallback_payload: NaN-safe contract ---

    def test_fallback_payload_structure(self):
        fn = self._make_coro(raise_exc=RateLimitError("429"))
        try:
            self.scheduler.execute_with_guard(fn, source="alpha_vantage")
        except RuntimeError:
            pass
        payload = self.scheduler.build_fallback_payload(
            event_name="CPI m/m",
            source="alpha_vantage"
        )
        # All numeric fields must be 0.0
        self.assertEqual(payload["metrics"]["macro_surprise_score"], 0.0)
        self.assertTrue(payload["metrics"]["warning_flag"])
        self.assertEqual(payload["data"]["actual"], 0.0)
        self.assertEqual(payload["data"]["consensus"], 0.0)
        # State correctly propagated
        self.assertEqual(payload["_scheduler"]["state"], "RATE_LIMITED")
        self.assertEqual(payload["_scheduler"]["source"], "alpha_vantage")
        self.assertEqual(payload["event_name"], "CPI m/m")

    # --- check_staleness: Non-blocking annotation ---

    def test_staleness_13_hour_event_is_stale(self):
        stale_dt = (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()
        self.assertTrue(self.scheduler.check_staleness(stale_dt))

    def test_staleness_1_hour_event_is_not_stale(self):
        fresh_dt = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        self.assertFalse(self.scheduler.check_staleness(fresh_dt))

    def test_staleness_none_input_returns_false(self):
        self.assertFalse(self.scheduler.check_staleness(None))

    def test_staleness_malformed_returns_false(self):
        self.assertFalse(self.scheduler.check_staleness("not-a-date"))

    # --- reset ---

    def test_reset_clears_state(self):
        fn = self._make_coro(raise_exc=RateLimitError("429"))
        try:
            self.scheduler.execute_with_guard(fn, source="test")
        except RuntimeError:
            pass
        self.assertEqual(self.scheduler.state, "RATE_LIMITED")
        self.scheduler.reset()
        self.assertEqual(self.scheduler.state, "OK")
        self.assertFalse(self.scheduler.stale_calendar_flag)


# ---------------------------------------------------------------------------
# MacroSurpriseCalibrationAgent Tests
# ---------------------------------------------------------------------------

class TestMacroSurpriseCalibrationAgent(unittest.TestCase):

    def setUp(self):
        self.agent = MacroSurpriseCalibrationAgent(cache_ttl_seconds=60)

    def test_known_indicator_fallback_returns_empirical_value(self):
        """When all retries fail, should return the known fallback for CPI."""
        with patch("functions.utils.macro.calibration_agent.run_async_in_thread", side_effect=Exception("mocked failure")):
            std, warning = self.agent.get_historical_std("CPI", window=12, api_key="test")
        self.assertAlmostEqual(std, 1.1410887363094182)
        self.assertTrue(warning)

    def test_unknown_indicator_fallback_returns_default_1(self):
        """Unknown indicators should fallback to 1.0."""
        with patch("functions.utils.macro.calibration_agent.run_async_in_thread", side_effect=Exception("mocked failure")):
            std, warning = self.agent.get_historical_std("UNKNOWN_IND", window=12, api_key="test")
        self.assertEqual(std, 1.0)
        self.assertTrue(warning)

    def test_cache_hit_skips_fetch(self):
        """Second call for same indicator should return from cache."""
        # Manually prime cache
        self.agent._set_cache("TESTIND", 2.5)
        with patch("functions.utils.macro.calibration_agent.run_async_in_thread") as mock_fetch:
            std, warning = self.agent.get_historical_std("TESTIND", window=12, api_key="test")
        mock_fetch.assert_not_called()
        self.assertEqual(std, 2.5)
        self.assertFalse(warning)

    def test_cache_ttl_expiry_triggers_refetch(self):
        """Expired cache entries should trigger a new fetch attempt."""
        agent = MacroSurpriseCalibrationAgent(cache_ttl_seconds=0)  # disable cache
        agent._set_cache("CPI", 1.5)  # manually set
        with patch("functions.utils.macro.calibration_agent.run_async_in_thread", side_effect=Exception("fail")):
            std, warning = agent.get_historical_std("CPI", window=12, api_key="test")
        # With TTL=0, cache is skipped — falls back to empirical value
        self.assertAlmostEqual(std, 1.1410887363094182)
        self.assertTrue(warning)


# ---------------------------------------------------------------------------
# audit_logger Tests
# ---------------------------------------------------------------------------

class TestExtractSchedulerBlock(unittest.TestCase):

    def test_extracts_scheduler_block(self):
        payload = {
            "event_name": "CPI m/m",
            "metrics": {"macro_surprise_score": 0.0},
            "_scheduler": {"state": "RATE_LIMITED", "source": "alpha_vantage"}
        }
        clean, meta = extract_scheduler_block(payload)
        self.assertNotIn("_scheduler", clean)
        self.assertEqual(meta["state"], "RATE_LIMITED")

    def test_no_scheduler_block_returns_none(self):
        payload = {"event_name": "CPI m/m", "metrics": {"macro_surprise_score": 0.0}}
        clean, meta = extract_scheduler_block(payload)
        self.assertIsNone(meta)
        self.assertIn("event_name", clean)

    def test_stale_payload_still_has_data(self):
        """A stale (but present) payload should still pass through to calculation."""
        scheduler = MacroScheduler()
        fn_success = None

        async def stale_fn():
            return [{"datetime_utc": (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()}]

        result = scheduler.execute_with_guard(stale_fn, source="forexfactory")
        is_stale = scheduler.check_staleness(result[0]["datetime_utc"])
        # State should still be OK — staleness is annotation only
        self.assertEqual(scheduler.state, "OK")
        self.assertTrue(is_stale)


if __name__ == "__main__":
    unittest.main()

"""Resilience helpers: market hours, stale quotes, circuit breaker."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.core import market_data as md

ET = ZoneInfo("America/New_York")


class TestMarketHours(unittest.TestCase):
    def setUp(self) -> None:
        md.reset_resilience_state()
        md.set_debug_overrides()

    def test_open_weekday_session(self) -> None:
        now = datetime(2026, 9, 2, 10, 0, tzinfo=ET)
        self.assertEqual(md.us_equity_market_status(now), "open")

    def test_closed_at_four_and_weekend(self) -> None:
        self.assertEqual(
            md.us_equity_market_status(datetime(2026, 9, 2, 16, 0, tzinfo=ET)),
            "closed",
        )
        self.assertEqual(
            md.us_equity_market_status(datetime(2026, 9, 5, 12, 0, tzinfo=ET)),
            "closed",
        )

    def test_closed_before_open(self) -> None:
        self.assertEqual(
            md.us_equity_market_status(datetime(2026, 9, 2, 9, 29, tzinfo=ET)),
            "closed",
        )


class TestStale(unittest.TestCase):
    def setUp(self) -> None:
        md.reset_resilience_state()
        md.set_debug_overrides()

    def test_stale_during_session_after_five_minutes(self) -> None:
        now = datetime(2026, 9, 2, 11, 0, tzinfo=ET)
        fetched = now - timedelta(minutes=6)
        fields = md.freshness_fields(fetched, from_cache=False, now=now)
        self.assertTrue(fields["stale"])
        self.assertEqual(fields["market_status"], "open")
        self.assertIsNotNone(fields["last_updated"])

    def test_fresh_during_session(self) -> None:
        now = datetime(2026, 9, 2, 11, 0, tzinfo=ET)
        fetched = now - timedelta(minutes=1)
        fields = md.freshness_fields(fetched, from_cache=False, now=now)
        self.assertFalse(fields["stale"])

    def test_old_print_not_stale_when_session_closed(self) -> None:
        now = datetime(2026, 9, 5, 12, 0, tzinfo=ET)
        fetched = now - timedelta(hours=20)
        fields = md.freshness_fields(fetched, from_cache=False, now=now)
        self.assertFalse(fields["stale"])
        self.assertEqual(fields["market_status"], "closed")

    def test_cache_fallback_is_stale(self) -> None:
        now = datetime(2026, 9, 5, 12, 0, tzinfo=ET)
        fetched = now - timedelta(minutes=1)
        fields = md.freshness_fields(fetched, from_cache=True, now=now)
        self.assertTrue(fields["stale"])


class TestCircuitBreaker(unittest.TestCase):
    def setUp(self) -> None:
        md.reset_resilience_state()
        md.set_debug_overrides()

    def test_stops_calling_provider_after_three_failures(self) -> None:
        quote = {
            "symbol": "AAPL",
            "price": 100.0,
            "volume": 1,
            "change_percent": 0.0,
            "previous_close": 100.0,
            "as_of": "2026-09-02",
        }
        with patch.object(md, "_parse_quote", return_value=quote):
            live = md.fetch_quote("AAPL")
        self.assertEqual(live["price"], 100.0)
        self.assertFalse(live["stale"])

        md.set_debug_overrides(force_fail=True)
        for _ in range(md.CIRCUIT_FAILURE_THRESHOLD):
            cached = md.fetch_quote("AAPL")
            self.assertTrue(cached["stale"])
            self.assertEqual(cached["price"], 100.0)

        md.set_debug_overrides()
        with patch.object(md, "_parse_quote", side_effect=AssertionError("provider hammered")):
            held = md.fetch_quote("AAPL")
        self.assertTrue(held["stale"])
        self.assertEqual(held["price"], 100.0)


if __name__ == "__main__":
    unittest.main()

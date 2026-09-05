"""NSE support: per-symbol currency + market-hours routing (no network needed)."""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core import market_data as md

ET = ZoneInfo("America/New_York")
IST = ZoneInfo("Asia/Kolkata")


class TestIsNseSymbol(unittest.TestCase):
    def test_ns_suffix_is_nse(self) -> None:
        self.assertTrue(md.is_nse_symbol("TCS.NS"))
        self.assertTrue(md.is_nse_symbol("tcs.ns"))

    def test_bo_suffix_is_nse(self) -> None:
        self.assertTrue(md.is_nse_symbol("RELIANCE.BO"))

    def test_plain_us_ticker_is_not_nse(self) -> None:
        self.assertFalse(md.is_nse_symbol("AAPL"))
        self.assertFalse(md.is_nse_symbol(""))


class TestCurrencyForSymbol(unittest.TestCase):
    def test_nse_symbol_is_inr(self) -> None:
        self.assertEqual(md.currency_for_symbol("INFY.NS"), "INR")

    def test_us_symbol_is_usd(self) -> None:
        self.assertEqual(md.currency_for_symbol("AAPL"), "USD")


class TestNseEquityMarketStatus(unittest.TestCase):
    def setUp(self) -> None:
        md.reset_resilience_state()
        md.set_debug_overrides()

    def test_open_during_weekday_session(self) -> None:
        # Wednesday 12:00pm IST — well inside 9:15-15:30.
        now = datetime(2026, 9, 2, 12, 0, tzinfo=IST)
        self.assertEqual(md.nse_equity_market_status(now), "open")

    def test_closed_before_open_and_after_close(self) -> None:
        self.assertEqual(
            md.nse_equity_market_status(datetime(2026, 9, 2, 9, 0, tzinfo=IST)),
            "closed",
        )
        self.assertEqual(
            md.nse_equity_market_status(datetime(2026, 9, 2, 15, 30, tzinfo=IST)),
            "closed",
        )

    def test_closed_on_weekend(self) -> None:
        # Saturday.
        self.assertEqual(
            md.nse_equity_market_status(datetime(2026, 9, 5, 12, 0, tzinfo=IST)),
            "closed",
        )


class TestMarketStatusForSymbol(unittest.TestCase):
    def setUp(self) -> None:
        md.reset_resilience_state()
        md.set_debug_overrides()

    def test_nse_symbol_uses_india_session_not_us(self) -> None:
        # 11:00am IST on a Wednesday: NSE is open, but it's 1:30am in New
        # York, hours before the US session opens. An NSE ticker must be
        # judged on its own exchange's clock, not the US one.
        now = datetime(2026, 9, 2, 11, 0, tzinfo=IST)
        self.assertEqual(md.market_status_for_symbol("TCS.NS", now), "open")
        self.assertEqual(md.us_equity_market_status(now), "closed")

    def test_us_symbol_uses_us_session(self) -> None:
        now = datetime(2026, 9, 2, 10, 0, tzinfo=ET)
        self.assertEqual(md.market_status_for_symbol("AAPL", now), "open")

    def test_debug_override_applies_to_both(self) -> None:
        md.set_debug_overrides(force_market="closed")
        now = datetime(2026, 9, 2, 12, 0, tzinfo=IST)
        self.assertEqual(md.market_status_for_symbol("TCS.NS", now), "closed")
        self.assertEqual(md.market_status_for_symbol("AAPL", now), "closed")


class TestFreshnessFieldsIncludesCurrencyAndSymbolAwareStatus(unittest.TestCase):
    def setUp(self) -> None:
        md.reset_resilience_state()
        md.set_debug_overrides()

    def test_nse_symbol_gets_inr_and_its_own_session(self) -> None:
        now = datetime(2026, 9, 2, 11, 0, tzinfo=IST)
        fields = md.freshness_fields(None, symbol="TCS.NS", from_cache=False, now=now)
        self.assertEqual(fields["currency"], "INR")
        self.assertEqual(fields["market_status"], "open")

    def test_us_symbol_gets_usd(self) -> None:
        now = datetime(2026, 9, 2, 10, 0, tzinfo=ET)
        fields = md.freshness_fields(None, symbol="AAPL", from_cache=False, now=now)
        self.assertEqual(fields["currency"], "USD")
        self.assertEqual(fields["market_status"], "open")


if __name__ == "__main__":
    unittest.main()

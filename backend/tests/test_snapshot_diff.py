"""Snapshot diff / first-visit tagging for GET /watchlists/{id}/changes."""

from __future__ import annotations

import unittest

from datetime import datetime, timedelta, timezone

from app.core.snapshot_diff import (
    apply_sector_flags,
    build_summary,
    diff_symbol,
    rank_changes,
    select_comparison_snapshot,
)


class TestDiffSymbol(unittest.TestCase):
    def test_no_snapshot_is_tracking_started_today(self) -> None:
        row = diff_symbol(
            "AAPL",
            snapshot=None,
            quote={"price": 190.0, "volume": 50_000_000},
            baseline={"mean_return": 0.01, "std_dev_return": 0.02, "avg_volume": 1.0, "avg_volatility": 0.01},
        )
        self.assertEqual(row["status"], "tracking_started_today")
        self.assertIsNone(row["attention_score"])
        self.assertIsNone(row["price_return"])
        self.assertEqual(row["current_price"], 190.0)

    def test_missing_quote(self) -> None:
        row = diff_symbol("ZZZZ", snapshot=None, quote=None, baseline=None)
        self.assertEqual(row["status"], "market_data_unavailable")
        self.assertIsNone(row["attention_score"])

    def test_compared_uses_snapshot_price_not_zero(self) -> None:
        row = diff_symbol(
            "MSFT",
            snapshot={"price": 100.0, "volume": 1_000_000, "timestamp": "2026-09-01T00:00:00+00:00"},
            quote={"price": 110.0, "volume": 2_000_000, "previous_close": 100.0, "high": 111.0, "low": 109.0},
            baseline={
                "mean_return": 0.01,
                "std_dev_return": 0.02,
                "avg_volume": 1_000_000,
                "avg_volatility": 0.02,
            },
            current_bar={"high": 111.0, "low": 109.0, "close": 110.0},
        )
        self.assertEqual(row["status"], "compared")
        self.assertAlmostEqual(row["price_return"], 0.10)
        self.assertIsNotNone(row["attention_score"])
        self.assertGreater(row["attention_score"], 0)


class TestRankChanges(unittest.TestCase):
    def test_sorts_by_attention_score_desc_and_first_visit_last(self) -> None:
        rows = [
            {"symbol": "NEW", "status": "tracking_started_today", "attention_score": None},
            {"symbol": "LOW", "status": "compared", "attention_score": 12.0},
            {"symbol": "HIGH", "status": "compared", "attention_score": 88.0},
        ]
        ranked = rank_changes(rows)
        self.assertEqual([row["symbol"] for row in ranked], ["HIGH", "LOW", "NEW"])


class TestSectorFlags(unittest.TestCase):
    def test_two_plus_same_sector_above_z_threshold_are_sector_correlation(self) -> None:
        rows = [
            {"symbol": "AAPL", "sector": "Technology", "status": "compared", "z_score": 2.0},
            {"symbol": "MSFT", "sector": "Technology", "status": "compared", "z_score": -1.8},
            {"symbol": "NVDA", "sector": "Technology", "status": "compared", "z_score": 0.4},
        ]
        tagged = apply_sector_flags(rows)
        by_symbol = {row["symbol"]: row["flag_type"] for row in tagged}
        self.assertEqual(by_symbol["AAPL"], "sector_correlation")
        self.assertEqual(by_symbol["MSFT"], "sector_correlation")
        self.assertEqual(by_symbol["NVDA"], "stock_specific")

    def test_below_threshold_or_different_sectors_stay_stock_specific(self) -> None:
        rows = [
            {"symbol": "AAPL", "sector": "Technology", "status": "compared", "z_score": 1.5},
            {"symbol": "MSFT", "sector": "Technology", "status": "compared", "z_score": 1.4},
            {"symbol": "NVDA", "sector": "Technology", "status": "compared", "z_score": 2.8},
            {"symbol": "XOM", "sector": "Energy", "status": "compared", "z_score": 2.0},
            {"symbol": "JPM", "sector": "Financials", "status": "compared", "z_score": -2.1},
        ]
        tagged = apply_sector_flags(rows)
        by_symbol = {row["symbol"]: row["flag_type"] for row in tagged}
        self.assertEqual(by_symbol["AAPL"], "stock_specific")
        self.assertEqual(by_symbol["MSFT"], "stock_specific")
        self.assertEqual(by_symbol["NVDA"], "stock_specific")
        self.assertEqual(by_symbol["XOM"], "stock_specific")
        self.assertEqual(by_symbol["JPM"], "stock_specific")

    def test_flags_compared_rows_only(self) -> None:
        rows = [
            {"symbol": "AAPL", "sector": "Technology", "status": "compared", "z_score": 2.0, "attention_score": 40},
            {"symbol": "MSFT", "sector": "Technology", "status": "compared", "z_score": 1.8, "attention_score": 35},
            {"symbol": "NEW", "sector": "Technology", "status": "tracking_started_today", "z_score": None, "attention_score": None},
        ]
        tagged = apply_sector_flags(rows)
        by_symbol = {row["symbol"]: row for row in tagged}
        self.assertEqual(by_symbol["AAPL"]["flag_type"], "sector_correlation")
        self.assertEqual(by_symbol["MSFT"]["flag_type"], "sector_correlation")
        self.assertIsNone(by_symbol["NEW"].get("flag_type"))


class TestSelectComparisonSnapshot(unittest.TestCase):
    def test_skips_fresh_dashboard_snapshot(self) -> None:
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        prior = {"price": 100.0, "timestamp": (now - timedelta(days=1)).isoformat()}
        just_written = {"price": 101.0, "timestamp": (now - timedelta(minutes=2)).isoformat()}
        chosen = select_comparison_snapshot([just_written, prior], now=now)
        self.assertEqual(chosen["price"], 100.0)

    def test_uses_latest_when_stale(self) -> None:
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        latest = {"price": 101.0, "timestamp": (now - timedelta(hours=6)).isoformat()}
        older = {"price": 90.0, "timestamp": (now - timedelta(days=2)).isoformat()}
        chosen = select_comparison_snapshot([latest, older], now=now)
        self.assertEqual(chosen["price"], 101.0)

    def test_empty(self) -> None:
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        self.assertIsNone(select_comparison_snapshot([], now=now))


def _compared_row(symbol, *, label, score, sector="", flag_type="stock_specific", price_return=0.01):
    return {
        "symbol": symbol,
        "sector": sector,
        "status": "compared",
        "attention_score": score,
        "attention_label": label,
        "flag_type": flag_type,
        "price_return": price_return,
    }


class TestBuildSummary(unittest.TestCase):
    def test_counts_by_label_and_total_flagged(self) -> None:
        rows = [
            _compared_row("AAPL", label="significant", score=92.0),
            _compared_row("MSFT", label="moderate", score=41.0),
            _compared_row("JPM", label="normal", score=8.0),
            {"symbol": "TSLA", "status": "tracking_started_today", "attention_score": None},
        ]
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        summary = build_summary(rows, previous_viewed=now - timedelta(hours=6), now=now)
        self.assertEqual(summary["counts"], {"significant": 1, "important": 0, "moderate": 1, "normal": 1})
        # tracking_started_today rows are excluded from total_compared / total_flagged
        self.assertEqual(summary["total_compared"], 3)
        self.assertEqual(summary["total_flagged"], 2)

    def test_top_mover_is_highest_attention_score(self) -> None:
        rows = [
            _compared_row("AAPL", label="moderate", score=41.0, price_return=0.02),
            _compared_row("NVDA", label="significant", score=92.0, price_return=0.08),
        ]
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        summary = build_summary(rows, previous_viewed=now - timedelta(hours=1), now=now)
        self.assertEqual(summary["top_mover"]["symbol"], "NVDA")
        self.assertEqual(summary["top_mover"]["attention_score"], 92.0)

    def test_no_scored_rows_top_mover_is_none(self) -> None:
        rows = [{"symbol": "AAPL", "status": "tracking_started_today", "attention_score": None}]
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        summary = build_summary(rows, previous_viewed=None, now=now)
        self.assertIsNone(summary["top_mover"])
        self.assertIsNone(summary["days_since_last_visit"])
        self.assertFalse(summary["is_digest"])

    def test_sector_groups_deduplicated_and_sorted(self) -> None:
        rows = [
            _compared_row("AAPL", label="significant", score=90.0, sector="Technology", flag_type="sector_correlation"),
            _compared_row("MSFT", label="important", score=70.0, sector="Technology", flag_type="sector_correlation"),
            _compared_row("JPM", label="moderate", score=40.0, sector="Financials", flag_type="sector_correlation"),
        ]
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        summary = build_summary(rows, previous_viewed=now - timedelta(hours=2), now=now)
        self.assertEqual(summary["sector_groups"], ["Financials", "Technology"])

    def test_is_digest_true_after_threshold_days(self) -> None:
        rows = [_compared_row("AAPL", label="moderate", score=41.0)]
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        summary = build_summary(rows, previous_viewed=now - timedelta(days=5), now=now)
        self.assertTrue(summary["is_digest"])
        self.assertAlmostEqual(summary["days_since_last_visit"], 5.0, places=1)

    def test_is_digest_false_within_threshold(self) -> None:
        rows = [_compared_row("AAPL", label="moderate", score=41.0)]
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        summary = build_summary(rows, previous_viewed=now - timedelta(hours=6), now=now)
        self.assertFalse(summary["is_digest"])


if __name__ == "__main__":
    unittest.main()

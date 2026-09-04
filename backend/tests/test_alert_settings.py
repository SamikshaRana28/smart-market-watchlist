"""Watchlist-level Alert Threshold: which symbols _triggered_alerts() flags."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.routes.watchlists import _triggered_alerts


def _watchlist(*, alerts_enabled: bool, alert_threshold: float | None) -> SimpleNamespace:
    # _triggered_alerts only reads these two attributes off the Watchlist ORM
    # object, so a plain namespace stands in fine without touching the DB.
    return SimpleNamespace(alerts_enabled=alerts_enabled, alert_threshold=alert_threshold)


def _row(symbol: str, score: float | None, status: str = "compared") -> dict:
    return {"symbol": symbol, "attention_score": score, "status": status}


class TestTriggeredAlerts(unittest.TestCase):
    def test_alerts_disabled_returns_nothing_even_above_threshold(self) -> None:
        watchlist = _watchlist(alerts_enabled=False, alert_threshold=50)
        rows = [_row("AAPL", 95)]
        self.assertEqual(_triggered_alerts(watchlist, rows), [])

    def test_no_threshold_set_returns_nothing(self) -> None:
        watchlist = _watchlist(alerts_enabled=True, alert_threshold=None)
        rows = [_row("AAPL", 95)]
        self.assertEqual(_triggered_alerts(watchlist, rows), [])

    def test_score_at_or_above_threshold_triggers(self) -> None:
        watchlist = _watchlist(alerts_enabled=True, alert_threshold=80)
        rows = [_row("AAPL", 80), _row("MSFT", 79.9), _row("NVDA", 95)]
        # 80 is inclusive (>=), 79.9 is not.
        self.assertEqual(_triggered_alerts(watchlist, rows), ["AAPL", "NVDA"])

    def test_first_visit_rows_without_a_score_are_ignored(self) -> None:
        watchlist = _watchlist(alerts_enabled=True, alert_threshold=30)
        rows = [_row("TSLA", None, status="tracking_started_today")]
        self.assertEqual(_triggered_alerts(watchlist, rows), [])

    def test_non_compared_status_is_ignored_even_with_a_score(self) -> None:
        watchlist = _watchlist(alerts_enabled=True, alert_threshold=30)
        rows = [_row("TSLA", 90, status="market_data_unavailable")]
        self.assertEqual(_triggered_alerts(watchlist, rows), [])


if __name__ == "__main__":
    unittest.main()
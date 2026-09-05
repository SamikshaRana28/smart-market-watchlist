"""Route-level tests for the /changes 'feed' block: cycle stats, the
force_disagree simulate flag, and graceful degradation on a total outage
with nothing cached (previously an uncaught exception — see
get_watchlist_changes in app.routes.watchlists).

Uses its own throwaway SQLite file so it never touches a real dev DB; the
env var must be set before app.db is imported anywhere (it builds the engine
at import time), so this happens at module load, before other app imports.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

from fastapi.testclient import TestClient  # noqa: E402

import main as main_module  # noqa: E402
from app.core import market_data as md  # noqa: E402
from app.db import Base, engine  # noqa: E402


def _fake_bars(symbol: str, trading_days: int = 20):
    price = 100.0
    bars = []
    for i in range(trading_days):
        price *= 1 + (0.001 if symbol != "DROP" else 0)
        bars.append({"close": round(price, 2), "volume": 1_000_000})
    return bars


class FeedStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(main_module.app)

    def setUp(self):
        md.reset_resilience_state()
        md.set_debug_overrides()
        resp = self.client.post(
            "/watchlists", json={"name": f"Feed test {id(self)}", "user_id": 4242, "symbols": []}
        )
        self.assertEqual(resp.status_code, 200)
        self.watchlist_id = resp.json()["id"]
        for symbol in ("AAPL", "MSFT"):
            r = self.client.post(f"/watchlists/{self.watchlist_id}/stocks", json={"symbol": symbol})
            self.assertEqual(r.status_code, 200)

    def test_feed_block_has_expected_shape_and_counts(self):
        with patch("app.routes.watchlists.fetch_ohlcv_status", side_effect=_fake_bars_status):
            resp = self.client.get(f"/watchlists/{self.watchlist_id}/changes")
        self.assertEqual(resp.status_code, 200)
        feed = resp.json()["feed"]
        self.assertEqual(feed["status"], "healthy")
        self.assertEqual(feed["applied"], 2)
        self.assertEqual(feed["rejected"], 0)
        self.assertEqual(feed["polling_interval_seconds"], 45)
        self.assertGreaterEqual(feed["cycle_time_ms"], 0)
        self.assertIsInstance(feed["headline_model"], str)
        self.assertGreaterEqual(feed["bars_fetched"], 2)

    def test_force_disagree_flag_surfaces_in_feed_status(self):
        with patch("app.routes.watchlists.fetch_ohlcv_status", side_effect=_fake_bars_status):
            resp = self.client.get(
                f"/watchlists/{self.watchlist_id}/changes", params={"force_disagree": "true"}
            )
        self.assertEqual(resp.status_code, 200)
        feed = resp.json()["feed"]
        self.assertTrue(feed["sources_disagree"])
        self.assertEqual(feed["status"], "disagree")

    def test_total_outage_with_no_cache_degrades_instead_of_500(self):
        # Every symbol is brand new (setUp) so there is nothing cached yet —
        # before the fix, a raised exception here propagated to a 500.
        def _always_fails(symbol, trading_days=20):
            raise RuntimeError("provider unreachable")

        with patch("app.routes.watchlists.fetch_ohlcv_status", side_effect=_always_fails):
            resp = self.client.get(f"/watchlists/{self.watchlist_id}/changes")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["feed"]["status"], "outage")
        self.assertEqual(body["feed"]["applied"], 0)
        self.assertEqual(body["feed"]["rejected"], 2)
        for row in body["changes"]:
            self.assertEqual(row["status"], "market_data_unavailable")


def _fake_bars_status(symbol: str, trading_days: int = 20):
    return {
        "bars": _fake_bars(symbol, trading_days),
        "stale": False,
        "last_updated": "2026-01-01T00:00:00+00:00",
        "market_status": "open",
        "sources_disagree": md.sources_disagree_forced(),
    }


if __name__ == "__main__":
    unittest.main()

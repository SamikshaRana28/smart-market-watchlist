"""Symbol autocomplete: search_symbols() helper backing GET /market/search."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core import market_data as md
from app.core.market_data import search_symbols


class TestSearchSymbols(unittest.TestCase):
    def setUp(self) -> None:
        # search_symbols() falls through to a real yf.Search() network call
        # whenever the curated local list doesn't fill the requested limit.
        # These tests only care about the local-match/ranking/dedup logic,
        # so the live lookup is patched out everywhere in this file — keeps
        # the suite's "no network required" guarantee true and these tests
        # fast and deterministic regardless of connectivity.
        patcher = patch.object(md, "_live_symbol_matches", return_value=[])
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_empty_query_returns_empty_list(self) -> None:
        self.assertEqual(search_symbols(""), [])
        self.assertEqual(search_symbols("   "), [])

    def test_alias_resolves_common_name_to_ticker(self) -> None:
        # The exact "typed GOOGLE, meant GOOGL" confusion this feature exists to fix.
        results = search_symbols("google")
        symbols = [r["symbol"] for r in results]
        self.assertIn("GOOGL", symbols)

    def test_prefix_match_ranks_before_substring_match(self) -> None:
        # "AAPL" itself should be the top hit for a query starting with "AAP".
        results = search_symbols("AAP")
        self.assertTrue(results)
        self.assertEqual(results[0]["symbol"], "AAPL")

    def test_limit_is_respected_and_clamped(self) -> None:
        results = search_symbols("a", limit=3)
        self.assertLessEqual(len(results), 3)
        # Absurd limit requests are clamped, not passed straight through.
        results_over = search_symbols("a", limit=999)
        self.assertLessEqual(len(results_over), 15)

    def test_no_duplicate_symbols_in_results(self) -> None:
        results = search_symbols("a", limit=15)
        symbols = [r["symbol"] for r in results]
        self.assertEqual(len(symbols), len(set(symbols)))


if __name__ == "__main__":
    unittest.main()
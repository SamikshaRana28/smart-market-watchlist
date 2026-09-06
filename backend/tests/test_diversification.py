"""Diversification metrics: returns, pairwise correlation, effective
independent bets, closest pair, largest sector, and addition suggestions.

Pure functions, no DB/network — mirrors the testing approach already used
for change_engine.py and accuracy.py.
"""

from __future__ import annotations

import unittest

from app.core.diversification import (
    adds_the_least,
    average_pairwise_correlation,
    build_correlation_matrix,
    closest_pair,
    effective_independent_bets,
    largest_sector,
    lookup_correlation,
    pearson_correlation,
    per_symbol_average_correlation,
    rank_addition_candidates,
    returns_from_closes,
)


class TestReturnsFromCloses(unittest.TestCase):
    def test_simple_series(self) -> None:
        returns = returns_from_closes([100, 110, 99])
        self.assertAlmostEqual(returns[0], 0.10)
        self.assertAlmostEqual(returns[1], -0.10)

    def test_fewer_than_two_closes_returns_empty(self) -> None:
        self.assertEqual(returns_from_closes([100]), [])
        self.assertEqual(returns_from_closes([]), [])

    def test_zero_previous_close_is_skipped_not_a_crash(self) -> None:
        # A zero close shouldn't raise a ZeroDivisionError and take down the
        # whole /diversification request over one bad bar.
        returns = returns_from_closes([0, 100, 110])
        self.assertEqual(len(returns), 1)
        self.assertAlmostEqual(returns[0], 0.10)


class TestPearsonCorrelation(unittest.TestCase):
    def test_identical_series_is_perfectly_correlated(self) -> None:
        series = [0.01, -0.02, 0.03, -0.01, 0.02]
        self.assertAlmostEqual(pearson_correlation(series, series), 1.0)

    def test_inverted_series_is_perfectly_anti_correlated(self) -> None:
        series = [0.01, -0.02, 0.03, -0.01, 0.02]
        inverted = [-x for x in series]
        self.assertAlmostEqual(pearson_correlation(series, inverted), -1.0)

    def test_fewer_than_three_overlapping_points_is_none(self) -> None:
        self.assertIsNone(pearson_correlation([0.01, 0.02], [0.01, 0.02]))

    def test_zero_variance_series_is_none_not_zero(self) -> None:
        # A flat (never-moving) return series has undefined correlation —
        # returning 0.0 here would misreport it as "independent" rather
        # than "we can't say".
        flat = [0.0, 0.0, 0.0, 0.0]
        moving = [0.01, -0.02, 0.03, -0.01]
        self.assertIsNone(pearson_correlation(flat, moving))

    def test_aligns_on_trailing_overlap_for_uneven_length_series(self) -> None:
        # Series b is a newly-added candidate with less history than the
        # held symbol a; correlation should still compute over the shared tail.
        a = [0.01, -0.02, 0.03, -0.01, 0.02]
        b = [0.03, -0.01, 0.02]
        self.assertIsNotNone(pearson_correlation(a, b))


class TestBuildCorrelationMatrixAndLookup(unittest.TestCase):
    def setUp(self) -> None:
        self.returns = {
            "AAPL": [0.01, -0.02, 0.03, -0.01, 0.02],
            "MSFT": [0.01, -0.02, 0.03, -0.01, 0.02],  # identical to AAPL
            "FLAT": [0.0, 0.0, 0.0, 0.0, 0.0],  # zero variance
        }
        self.matrix = build_correlation_matrix(self.returns)

    def test_perfectly_correlated_pair_is_present(self) -> None:
        self.assertAlmostEqual(lookup_correlation("AAPL", "MSFT", self.matrix), 1.0)

    def test_lookup_is_symmetric_regardless_of_insertion_order(self) -> None:
        self.assertEqual(
            lookup_correlation("AAPL", "MSFT", self.matrix),
            lookup_correlation("MSFT", "AAPL", self.matrix),
        )

    def test_self_correlation_is_always_one(self) -> None:
        self.assertEqual(lookup_correlation("AAPL", "AAPL", self.matrix), 1.0)

    def test_zero_variance_pair_is_omitted_not_zero(self) -> None:
        self.assertIsNone(lookup_correlation("AAPL", "FLAT", self.matrix))


class TestAveragePairwiseCorrelation(unittest.TestCase):
    def test_empty_matrix_is_none(self) -> None:
        self.assertIsNone(average_pairwise_correlation({}))

    def test_averages_all_pairs(self) -> None:
        matrix = {("A", "B"): 0.2, ("A", "C"): 0.4, ("B", "C"): 0.6}
        self.assertAlmostEqual(average_pairwise_correlation(matrix), 0.4)


class TestEffectiveIndependentBets(unittest.TestCase):
    def test_matches_the_worked_example(self) -> None:
        # 15 names, avg correlation 0.24 -> ~3.44, matches the "3.5
        # independent bets across 15 names" reference this was built from.
        self.assertAlmostEqual(effective_independent_bets(15, 0.24), 3.44, places=2)

    def test_perfect_correlation_collapses_to_one_bet(self) -> None:
        self.assertAlmostEqual(effective_independent_bets(10, 1.0), 1.0)

    def test_zero_correlation_gives_full_independence(self) -> None:
        self.assertAlmostEqual(effective_independent_bets(10, 0.0), 10.0)

    def test_missing_correlation_data_assumes_fully_independent(self) -> None:
        self.assertEqual(effective_independent_bets(5, None), 5.0)

    def test_empty_book_is_zero(self) -> None:
        self.assertEqual(effective_independent_bets(0, None), 0.0)

    def test_result_never_exceeds_n_even_with_negative_correlation(self) -> None:
        # A book can't have more independent bets than names in it, even
        # when a negative average correlation would push the raw ratio above n.
        bets = effective_independent_bets(4, -0.9)
        self.assertLessEqual(bets, 4.0)


class TestClosestPair(unittest.TestCase):
    def test_empty_matrix_is_none(self) -> None:
        self.assertIsNone(closest_pair({}))

    def test_picks_the_highest_correlation_pair(self) -> None:
        matrix = {("A", "B"): 0.2, ("A", "C"): 0.9, ("B", "C"): 0.5}
        pair = closest_pair(matrix)
        self.assertEqual({pair["a"], pair["b"]}, {"A", "C"})
        self.assertAlmostEqual(pair["correlation"], 0.9)


class TestAddsTheLeast(unittest.TestCase):
    def test_picks_symbol_with_lowest_average_correlation(self) -> None:
        # C is lightly correlated to both A and B; A and B are tightly
        # correlated to each other. C should come out as "adds the least".
        matrix = {("A", "B"): 0.9, ("A", "C"): 0.1, ("B", "C"): 0.2}
        result = adds_the_least(["A", "B", "C"], matrix)
        self.assertEqual(result[0], "C")

    def test_no_correlation_data_is_none(self) -> None:
        self.assertIsNone(adds_the_least(["A", "B"], {}))


class TestPerSymbolAverageCorrelation(unittest.TestCase):
    def test_averages_only_pairs_involving_the_symbol(self) -> None:
        matrix = {("A", "B"): 0.2, ("A", "C"): 0.6, ("B", "C"): 0.9}
        result = per_symbol_average_correlation(["A", "B", "C"], matrix)
        self.assertAlmostEqual(result["A"], 0.4)  # (0.2 + 0.6) / 2


class TestLargestSector(unittest.TestCase):
    def test_picks_the_majority_sector_and_its_share(self) -> None:
        sectors = {"AAPL": "Technology", "MSFT": "Technology", "JPM": "Financials"}
        sector, pct = largest_sector(sectors)
        self.assertEqual(sector, "Technology")
        self.assertAlmostEqual(pct, 200 / 3)

    def test_blank_sectors_are_ignored(self) -> None:
        sectors = {"AAPL": "Technology", "UNKNOWN": "", "ALSO_UNKNOWN": "   "}
        sector, pct = largest_sector(sectors)
        self.assertEqual(sector, "Technology")
        self.assertAlmostEqual(pct, 100.0)

    def test_all_blank_is_none(self) -> None:
        self.assertIsNone(largest_sector({"A": "", "B": ""}))


class TestRankAdditionCandidates(unittest.TestCase):
    def test_ranks_ascending_by_correlation_to_the_held_book(self) -> None:
        held = {"AAPL": [0.01, -0.02, 0.03, -0.01, 0.02]}
        candidates = {
            "MSFT": [0.01, -0.02, 0.03, -0.01, 0.02],  # identical -> corr 1.0
            "GOLD": [-0.01, 0.02, -0.03, 0.01, -0.02],  # inverted -> corr -1.0
        }
        ranked = rank_addition_candidates(candidates, held, limit=3)
        self.assertEqual(ranked[0]["symbol"], "GOLD")  # least correlated first
        self.assertEqual(ranked[1]["symbol"], "MSFT")

    def test_respects_limit(self) -> None:
        held = {"AAPL": [0.01, -0.02, 0.03, -0.01, 0.02]}
        candidates = {
            f"SYM{i}": [0.01 * i, -0.02, 0.03, -0.01, 0.02] for i in range(1, 6)
        }
        ranked = rank_addition_candidates(candidates, held, limit=2)
        self.assertEqual(len(ranked), 2)

    def test_candidate_with_no_overlap_is_excluded(self) -> None:
        held = {"AAPL": [0.01, -0.02]}  # too short to overlap 3+ points
        candidates = {"MSFT": [0.01, -0.02, 0.03]}
        self.assertEqual(rank_addition_candidates(candidates, held), [])


if __name__ == "__main__":
    unittest.main()

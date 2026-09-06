"""Score Accuracy Tracker: is_due_for_evaluation / compute_outcome_return /
did_move_further / summarize.

Pure functions, no DB — mirrors the testing approach already used for
change_engine.py and diversification.py.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.core.accuracy import (
    EVALUATION_WINDOW_DAYS,
    MOVED_FURTHER_THRESHOLD,
    compute_outcome_return,
    did_move_further,
    is_due_for_evaluation,
    summarize,
)


class TestIsDueForEvaluation(unittest.TestCase):
    def test_window_is_a_real_multi_day_gap_not_zero(self) -> None:
        # The whole point of this tracker is "did it move further a few
        # trading days later" — a same-visit or same-poll evaluation
        # (window=0) would grade the score against itself moments after
        # flagging it, which is what the earlier version of this constant
        # accidentally did.
        self.assertGreater(EVALUATION_WINDOW_DAYS, 0)

    def test_not_due_before_window_elapses(self) -> None:
        now = datetime(2026, 1, 10, tzinfo=timezone.utc)
        flagged_at = now - timedelta(days=EVALUATION_WINDOW_DAYS - 1)
        self.assertFalse(is_due_for_evaluation(flagged_at, now))

    def test_due_exactly_at_window(self) -> None:
        now = datetime(2026, 1, 10, tzinfo=timezone.utc)
        flagged_at = now - timedelta(days=EVALUATION_WINDOW_DAYS)
        self.assertTrue(is_due_for_evaluation(flagged_at, now))

    def test_due_well_after_window(self) -> None:
        now = datetime(2026, 1, 10, tzinfo=timezone.utc)
        flagged_at = now - timedelta(days=EVALUATION_WINDOW_DAYS + 10)
        self.assertTrue(is_due_for_evaluation(flagged_at, now))


class TestComputeOutcomeReturn(unittest.TestCase):
    def test_positive_move(self) -> None:
        self.assertAlmostEqual(compute_outcome_return(100.0, 110.0), 0.10)

    def test_negative_move(self) -> None:
        self.assertAlmostEqual(compute_outcome_return(100.0, 90.0), -0.10)

    def test_zero_price_at_flag_returns_none(self) -> None:
        # Avoids a ZeroDivisionError for a malformed/zero-priced flag rather
        # than crashing the whole /accuracy evaluation loop over one row.
        self.assertIsNone(compute_outcome_return(0.0, 100.0))


class TestDidMoveFurther(unittest.TestCase):
    def test_none_outcome_is_none_not_false(self) -> None:
        # Not-yet-evaluated should stay "unknown", not silently count as a miss.
        self.assertIsNone(did_move_further(None))

    def test_below_threshold_is_false(self) -> None:
        self.assertFalse(did_move_further(MOVED_FURTHER_THRESHOLD - 0.01))

    def test_at_threshold_is_true(self) -> None:
        self.assertTrue(did_move_further(MOVED_FURTHER_THRESHOLD))

    def test_negative_move_past_threshold_counts_too(self) -> None:
        # A flagged name that dropped hard afterward is just as much a hit
        # as one that ran up — "moved further" is direction-agnostic.
        self.assertTrue(did_move_further(-0.05))


def _event(label="Moderate", evaluated=True, outcome=None):
    return {"attention_label": label, "evaluated": evaluated, "outcome_return": outcome}


class TestSummarize(unittest.TestCase):
    def test_empty_events(self) -> None:
        result = summarize([])
        self.assertEqual(result["total_flagged"], 0)
        self.assertEqual(result["total_evaluated"], 0)
        self.assertEqual(result["pending_evaluation"], 0)
        self.assertIsNone(result["hit_rate"])

    def test_pending_events_excluded_from_hit_rate(self) -> None:
        events = [
            _event(evaluated=True, outcome=0.05),
            _event(evaluated=False, outcome=None),
        ]
        result = summarize(events)
        self.assertEqual(result["total_flagged"], 2)
        self.assertEqual(result["total_evaluated"], 1)
        self.assertEqual(result["pending_evaluation"], 1)
        self.assertEqual(result["hit_rate"], 1.0)

    def test_hit_rate_mixes_hits_and_misses(self) -> None:
        events = [
            _event(evaluated=True, outcome=0.05),   # hit (>= 3%)
            _event(evaluated=True, outcome=0.01),   # miss (< 3%)
            _event(evaluated=True, outcome=-0.10),  # hit (direction-agnostic)
        ]
        result = summarize(events)
        self.assertEqual(result["moved_further"], 2)
        self.assertAlmostEqual(result["hit_rate"], 2 / 3)

    def test_by_label_breakdown_is_isolated_per_label(self) -> None:
        events = [
            _event(label="Moderate", evaluated=True, outcome=0.05),
            _event(label="Significant", evaluated=True, outcome=0.01),
        ]
        result = summarize(events)
        self.assertEqual(result["by_label"]["Moderate"]["hit_rate"], 1.0)
        self.assertEqual(result["by_label"]["Significant"]["hit_rate"], 0.0)
        self.assertIsNone(result["by_label"]["Important"]["hit_rate"])

    def test_window_and_threshold_are_echoed_for_the_frontend(self) -> None:
        result = summarize([])
        self.assertEqual(result["window_days"], EVALUATION_WINDOW_DAYS)
        self.assertEqual(result["threshold"], MOVED_FURTHER_THRESHOLD)


if __name__ == "__main__":
    unittest.main()

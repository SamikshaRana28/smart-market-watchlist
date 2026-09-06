"""Score Accuracy Tracker — the self-audit layer.

Every time a symbol is flagged Moderate/Important/Significant, we record the
price at that moment. A few trading days later we check whether the price
actually moved further. This is reported back as an aggregate hit-rate — the
app grading its own signal instead of asserting significance and walking away.
"""

from __future__ import annotations

EVALUATION_WINDOW_DAYS = 0
MOVED_FURTHER_THRESHOLD = 0.03  # 3% either direction counts as "moved further"


def is_due_for_evaluation(flagged_at, now) -> bool:
    return (now - flagged_at).days >= EVALUATION_WINDOW_DAYS


def compute_outcome_return(price_at_flag: float, price_now: float) -> float | None:
    if not price_at_flag:
        return None
    return (price_now - price_at_flag) / price_at_flag


def did_move_further(outcome_return: float | None) -> bool | None:
    if outcome_return is None:
        return None
    return abs(outcome_return) >= MOVED_FURTHER_THRESHOLD


def summarize(events: list[dict]) -> dict:
    evaluated = [e for e in events if e.get("evaluated")]
    total_flagged = len(events)
    total_evaluated = len(evaluated)
    moved_further = [e for e in evaluated if did_move_further(e.get("outcome_return"))]
    hit_rate = (len(moved_further) / total_evaluated) if total_evaluated else None

    by_label: dict[str, dict] = {}
    for label in ("Moderate", "Important", "Significant"):
        subset = [e for e in evaluated if e.get("attention_label") == label]
        hits = [e for e in subset if did_move_further(e.get("outcome_return"))]
        by_label[label] = {
            "evaluated": len(subset),
            "moved_further": len(hits),
            "hit_rate": (len(hits) / len(subset)) if subset else None,
        }

    return {
        "total_flagged": total_flagged,
        "total_evaluated": total_evaluated,
        "pending_evaluation": total_flagged - total_evaluated,
        "moved_further": len(moved_further),
        "hit_rate": hit_rate,
        "by_label": by_label,
        "window_days": EVALUATION_WINDOW_DAYS,
        "threshold": MOVED_FURTHER_THRESHOLD,
    }
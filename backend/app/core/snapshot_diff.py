"""Turn last-visit snapshots + current market data into ranked Attention Scores.

Kept free of SQLAlchemy so the first-visit vs compared branches can be unit-tested
without a database. Routes load snapshots/quotes and call these helpers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from app.core.change_engine import (
    DEFAULT_THRESHOLDS,
    calculate_attention_score,
    calculate_return,
    calculate_sector_correlation,
    calculate_volatility_ratio,
    calculate_volume_ratio,
    calculate_z_score,
    classify_attention,
)


def _session_volatility(bar: Mapping[str, Any] | None, close: float | None) -> float | None:
    if not bar or not close:
        return None
    high = bar.get("high")
    low = bar.get("low")
    if high is None or low is None:
        return None
    return abs(float(high) - float(low)) / close


def diff_symbol(
    symbol: str,
    *,
    sector: str = "",
    snapshot: Mapping[str, Any] | None,
    quote: Mapping[str, Any] | None,
    baseline: Mapping[str, Any] | None,
    current_bar: Mapping[str, Any] | None = None,
    thresholds: tuple[float, float, float] = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    """Build one watchlist change row.

    No prior snapshot → `tracking_started_today` (never a fake 0→price return).
    No current quote → `market_data_unavailable`.
    `thresholds` lets the caller apply a sensitivity preset (see
    change_engine.SENSITIVITY_PRESETS) instead of the default 30/60/80 cutoffs.
    """
    ticker = symbol.strip().upper()

    if quote is None:
        return {
            "symbol": ticker,
            "sector": sector,
            "status": "market_data_unavailable",
            "attention_score": None,
            "attention_label": None,
            "price_return": None,
            "z_score": None,
            "volume_ratio": None,
            "volatility_ratio": None,
            "flag_type": None,
            "current_price": None,
            "previous_price": None if snapshot is None else snapshot.get("price"),
            "current_volume": None,
            "snapshot_at": None if snapshot is None else snapshot.get("timestamp"),
            "breakdown": None,
        }

    current_price = float(quote["price"])
    current_volume = int(quote.get("volume") or 0)

    if snapshot is None:
        return {
            "symbol": ticker,
            "sector": sector,
            "status": "tracking_started_today",
            "attention_score": None,
            "attention_label": None,
            "price_return": None,
            "z_score": None,
            "volume_ratio": None,
            "volatility_ratio": None,
            "flag_type": None,
            "current_price": current_price,
            "previous_price": None,
            "current_volume": current_volume,
            "snapshot_at": None,
            "breakdown": None,
        }

    previous_price = float(snapshot["price"])
    price_return = calculate_return(current_price, previous_price)

    previous_close = quote.get("previous_close")
    todays_return = calculate_return(current_price, float(previous_close)) if previous_close else price_return
    if todays_return is None:
        todays_return = 0.0

    mean_return = float(baseline["mean_return"]) if baseline else 0.0
    std_dev = float(baseline["std_dev_return"]) if baseline else 0.0
    avg_volume = float(baseline["avg_volume"]) if baseline else 0.0
    avg_volatility = float(baseline["avg_volatility"]) if baseline else 0.0

    z_score = calculate_z_score(todays_return, mean_return, std_dev)
    volume_ratio = calculate_volume_ratio(current_volume, avg_volume)
    current_vol = _session_volatility(current_bar or quote, current_price)
    volatility_ratio = calculate_volatility_ratio(current_vol, avg_volatility) if current_vol is not None else None

    if price_return is None:
        price_return = 0.0

    breakdown = calculate_attention_score(
        price_return=price_return,
        z_score=z_score,
        volume_ratio=volume_ratio,
        volatility_ratio=volatility_ratio,
    )

    return {
        "symbol": ticker,
        "sector": sector,
        "status": "compared",
        "attention_score": breakdown["attention_score"],
        "attention_label": classify_attention(breakdown["attention_score"], thresholds),
        "price_return": round(price_return, 8),
        "z_score": round(z_score, 6),
        "volume_ratio": None if volume_ratio is None else round(volume_ratio, 6),
        "volatility_ratio": None if volatility_ratio is None else round(volatility_ratio, 6),
        "flag_type": "stock_specific",
        "current_price": current_price,
        "previous_price": previous_price,
        "current_volume": current_volume,
        "snapshot_at": snapshot.get("timestamp"),
        "breakdown": breakdown,
    }


def apply_sector_flags(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    compared = [row for row in rows if row.get("status") == "compared" and row.get("z_score") is not None]
    if not compared:
        return list(rows)
    flags = calculate_sector_correlation(compared)
    tagged = []
    for row in rows:
        updated = dict(row)
        if updated.get("status") == "compared":
            updated["flag_type"] = flags.get(updated["symbol"], "stock_specific")
        tagged.append(updated)
    return tagged


def rank_changes(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by attention_score descending; unscored rows (first visit) go last."""

    def sort_key(row: Mapping[str, Any]) -> tuple[int, float]:
        score = row.get("attention_score")
        if score is None:
            return (0, 0.0)
        return (1, float(score))

    return sorted(rows, key=sort_key, reverse=True)


def _as_aware(ts: datetime | str) -> datetime:
    if isinstance(ts, str):
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    else:
        parsed = ts
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def select_comparison_snapshot(
    snapshots: Sequence[Mapping[str, Any]],
    *,
    now: datetime,
    fresh_window_seconds: int = 1800,
) -> Mapping[str, Any] | None:
    """Pick the snapshot that represents 'last visit'.

    GET /watchlists/{id}/changes writes a snapshot on every dashboard load. If
    the newest row is still inside `fresh_window_seconds`, skip it and use the
    previous one so the detail page does not compare a price to itself.
    """
    if not snapshots:
        return None

    ordered = sorted(snapshots, key=lambda row: _as_aware(row["timestamp"]), reverse=True)
    latest = ordered[0]
    now_aware = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    age = (now_aware - _as_aware(latest["timestamp"])).total_seconds()
    if len(ordered) >= 2 and age < fresh_window_seconds:
        return ordered[1]
    return latest

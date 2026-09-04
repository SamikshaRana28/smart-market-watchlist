"""Meaningful Change Engine — explainable Attention Score (not ML).

Each helper takes numbers in and returns numbers or plain dicts. No DB, Redis,
or yfinance calls live here so judges can step through the math in isolation.

Normalization caps (0–100) are explicit constants: a 10% price move, |z|=3,
3× volume, and 3× volatility each map to 100. Those caps are product choices,
not predictions — they turn unbounded ratios into a comparable attention scale.
"""

from __future__ import annotations

from typing import Literal, Mapping, Sequence, TypedDict

AttentionLabel = Literal["normal", "moderate", "important", "significant"]
FlagType = Literal["sector_correlation", "stock_specific"]

# Weighted mix — price is the user-facing move; z-score normalizes vs the
# stock's own history; volume confirms participation; volatility is secondary.
PRICE_WEIGHT = 0.35
Z_SCORE_WEIGHT = 0.30
VOLUME_WEIGHT = 0.20
VOLATILITY_WEIGHT = 0.15

# Linear caps used when stretching raw signals onto 0–100.
PRICE_RETURN_CAP = 0.10  # |return| of 10% → 100
Z_SCORE_CAP = 3.0  # |z| of 3 → 100 (beyond |z|>2.5 is already "significant")
RATIO_NORMAL = 1.0  # 1× average volume/vol is "nothing unusual"
RATIO_CAP = 3.0  # 3× average → 100

SECTOR_Z_THRESHOLD = 1.5
SECTOR_MIN_STOCKS = 2


class StockZSignal(TypedDict):
    symbol: str
    sector: str
    z_score: float


class AttentionBreakdown(TypedDict):
    attention_score: float
    price_score: float
    z_score_normalized: float
    volume_score: float
    volatility_score: float


def calculate_return(current_price: float, previous_price: float) -> float | None:
    """Simple close-to-close return: (current - previous) / previous.

    Returns None when previous_price is 0 or missing so we never invent a move.
    """
    if previous_price is None or current_price is None:
        return None
    if previous_price == 0:
        return None
    return (current_price - previous_price) / previous_price


def calculate_z_score(
    todays_return: float,
    mean_return: float,
    std_dev_return: float,
) -> float:
    """How abnormal today's return is vs the 20-day return distribution.

    z = (today - μ) / σ. σ = 0 means a flat baseline: z is 0 if today matches μ,
    otherwise we return a large sentinel (Z_SCORE_CAP) so a first real move is
    treated as unusual rather than crashing on divide-by-zero.
    """
    if std_dev_return == 0:
        if todays_return == mean_return:
            return 0.0
        return Z_SCORE_CAP if todays_return > mean_return else -Z_SCORE_CAP
    return (todays_return - mean_return) / std_dev_return


def calculate_volume_ratio(todays_volume: float, avg_volume: float) -> float | None:
    """today's volume / 20-day average volume.

    None when average volume is 0 (no baseline to compare against).
    """
    if avg_volume == 0:
        return None
    return todays_volume / avg_volume


def calculate_volatility_ratio(
    current_volatility: float,
    avg_volatility: float,
) -> float | None:
    """current session volatility / 20-day average volatility.

    None when the baseline volatility is 0.
    """
    if avg_volatility == 0:
        return None
    return current_volatility / avg_volatility


def _clamp_0_100(value: float) -> float:
    return max(0.0, min(100.0, value))


def _normalize_abs(value: float, cap: float) -> float:
    """Map |value| linearly onto 0–100, saturating at `cap`."""
    if cap <= 0:
        return 0.0
    return _clamp_0_100(abs(value) / cap * 100.0)


def _normalize_ratio_spike(ratio: float | None) -> float:
    """Map a 1×–3× ratio onto 0–100. At-or-below average scores 0 (not unusual)."""
    if ratio is None:
        return 0.0
    span = RATIO_CAP - RATIO_NORMAL
    if span <= 0:
        return 0.0
    return _clamp_0_100((ratio - RATIO_NORMAL) / span * 100.0)


def calculate_attention_score(
    price_return: float,
    z_score: float,
    volume_ratio: float | None,
    volatility_ratio: float | None,
) -> AttentionBreakdown:
    """Normalize the four signals to 0–100, then apply the Attention Score weights.

    attention_score = 0.35 * price + 0.30 * z + 0.20 * volume + 0.15 * volatility

    Price and z use absolute magnitude (a crash deserves as much attention as a
    spike). Volume and volatility only score *above* their 20-day average.
    """
    price_score = _normalize_abs(price_return, PRICE_RETURN_CAP)
    z_score_normalized = _normalize_abs(z_score, Z_SCORE_CAP)
    volume_score = _normalize_ratio_spike(volume_ratio)
    volatility_score = _normalize_ratio_spike(volatility_ratio)

    attention_score = (
        PRICE_WEIGHT * price_score
        + Z_SCORE_WEIGHT * z_score_normalized
        + VOLUME_WEIGHT * volume_score
        + VOLATILITY_WEIGHT * volatility_score
    )

    return {
        "attention_score": round(_clamp_0_100(attention_score), 4),
        "price_score": round(price_score, 4),
        "z_score_normalized": round(z_score_normalized, 4),
        "volume_score": round(volume_score, 4),
        "volatility_score": round(volatility_score, 4),
    }


DEFAULT_THRESHOLDS = (30.0, 60.0, 80.0)

# Sensitivity presets for classify_attention: (moderate_at, important_at, significant_at).
# Conservative needs a bigger move before it flags anything; Aggressive flags sooner.
SENSITIVITY_PRESETS: dict[str, tuple[float, float, float]] = {
    "conservative": (40.0, 65.0, 85.0),
    "balanced": DEFAULT_THRESHOLDS,
    "aggressive": (20.0, 45.0, 70.0),
}


def classify_attention(
    attention_score: float,
    thresholds: tuple[float, float, float] = DEFAULT_THRESHOLDS,
) -> AttentionLabel:
    """Bucket a 0–100 score into a human label (and implied color).

    Default 0–30 normal (green), 30–60 moderate (yellow),
    60–80 important (orange), 80–100 significant (red).

    Boundaries belong to the higher bucket. `thresholds` lets callers swap in
    a different sensitivity preset (see SENSITIVITY_PRESETS) without touching
    the underlying score math.
    """
    moderate_at, important_at, significant_at = thresholds
    if attention_score < moderate_at:
        return "normal"
    if attention_score < important_at:
        return "moderate"
    if attention_score < significant_at:
        return "important"
    return "significant"


def calculate_sector_correlation(
    stocks: Sequence[Mapping[str, object]],
) -> dict[str, FlagType]:
    """Tag names as sector-wide vs stock-specific using today's z-scores.

    If 2+ stocks in the same sector have |z| > 1.5, those names are
    `sector_correlation` (a sector move, not an idiosyncratic story).
    Everyone else is `stock_specific`. Input is assumed to be the same day
    and the same watchlist.
    """
    by_sector: dict[str, list[str]] = {}
    for row in stocks:
        symbol = str(row["symbol"])
        z_score = float(row["z_score"])  # type: ignore[arg-type]
        sector = str(row.get("sector") or "")
        if abs(z_score) > SECTOR_Z_THRESHOLD and sector:
            by_sector.setdefault(sector, []).append(symbol)

    correlated: set[str] = set()
    for symbols in by_sector.values():
        if len(symbols) >= SECTOR_MIN_STOCKS:
            correlated.update(symbols)

    flags: dict[str, FlagType] = {}
    for row in stocks:
        symbol = str(row["symbol"])
        flags[symbol] = (
            "sector_correlation" if symbol in correlated else "stock_specific"
        )
    return flags

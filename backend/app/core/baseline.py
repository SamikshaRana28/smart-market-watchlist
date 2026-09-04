"""20-day statistical baseline for the Attention Score engine.

`compute_baseline` is pure (list of bars in → stats dict out) so it can be
tested without Redis or yfinance. `get_baseline` wraps that with a per-symbol
Redis cache (24h TTL) because these stats only need a daily recompute.
"""

from __future__ import annotations

import json
import os
import statistics
from typing import Any, Mapping, Sequence

import redis

from app.core.market_data import fetch_ohlcv

BASELINE_TTL_SECONDS = 24 * 60 * 60
_REDIS_KEY_PREFIX = "baseline:"

_redis_client: redis.Redis | None = None


def _price(bar: Mapping[str, Any]) -> float | None:
    raw = bar.get("close", bar.get("price"))
    if raw is None:
        return None
    value = float(raw)
    if value != value:  # NaN
        return None
    return value


def _daily_range_volatility(bar: Mapping[str, Any], close: float) -> float | None:
    """True-range style vol: (high - low) / close, when OHLC is available."""
    high = bar.get("high")
    low = bar.get("low")
    if high is None or low is None or not close:
        return None
    return abs(float(high) - float(low)) / close


def compute_baseline(bars: Sequence[Mapping[str, Any]]) -> dict[str, float] | None:
    """Compute μ/σ of returns, average volume, and average daily volatility.

    Daily return uses consecutive closes: (p_t - p_{t-1}) / p_{t-1}.
    Volatility is the session range (high-low)/close when those fields exist;
    otherwise it falls back to |return| so price/volume-only series still work.

    Returns None when there are fewer than two valid prices (no return series,
    which is the 'Tracking started today' case).
    """
    prices: list[float] = []
    volumes: list[float] = []
    range_vols: list[float] = []

    for bar in bars:
        price = _price(bar)
        if price is None:
            continue
        prices.append(price)
        volume = bar.get("volume")
        if volume is not None:
            volumes.append(float(volume))
        range_vol = _daily_range_volatility(bar, price)
        if range_vol is not None:
            range_vols.append(range_vol)

    if len(prices) < 2:
        return None

    returns: list[float] = []
    for prev, curr in zip(prices, prices[1:]):
        if prev:
            returns.append((curr - prev) / prev)

    if not returns:
        return None

    mean_return = statistics.mean(returns)
    std_dev_return = statistics.stdev(returns) if len(returns) >= 2 else 0.0
    avg_volume = statistics.mean(volumes) if volumes else 0.0

    if range_vols:
        avg_volatility = statistics.mean(range_vols)
    else:
        avg_volatility = statistics.mean(abs(r) for r in returns)

    return {
        "mean_return": round(mean_return, 8),
        "std_dev_return": round(std_dev_return, 8),
        "avg_volume": round(avg_volume, 4),
        "avg_volatility": round(avg_volatility, 8),
        "sample_days": len(prices),
    }


def _redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _redis_client


def _cache_key(symbol: str) -> str:
    return f"{_REDIS_KEY_PREFIX}{symbol.strip().upper()}"


def get_baseline(
    symbol: str,
    bars: Sequence[Mapping[str, Any]] | None = None,
    *,
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    """Return the 20-day baseline for `symbol`, cached in Redis for 24 hours.

    On a cache hit, the stored stats are returned without recomputing.
    On a miss (or `force_refresh`), uses `bars` if provided, otherwise fetches
    the last 20 sessions via yfinance. Redis failures are ignored so a down
    cache never blocks a live compute.
    """
    ticker = symbol.strip().upper()
    key = _cache_key(ticker)

    if not force_refresh:
        try:
            cached = _redis().get(key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    history = list(bars) if bars is not None else fetch_ohlcv(ticker)
    if not history:
        return None

    stats = compute_baseline(history)
    if stats is None:
        return None

    payload = {"symbol": ticker, **stats}

    try:
        _redis().setex(key, BASELINE_TTL_SECONDS, json.dumps(payload))
    except Exception:
        pass

    return payload

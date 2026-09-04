"""yfinance market-data helpers.

These functions talk to the external data source and return plain dicts/lists.
Routes and later baseline jobs should call this module — not yfinance directly —
so retry behavior, circuit breaking, and empty-result handling stay in one place.
"""

from __future__ import annotations

import os
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timezone
from typing import Any, Callable, Literal, TypeVar
from zoneinfo import ZoneInfo

import yfinance as yf

T = TypeVar("T")
MarketStatus = Literal["open", "closed"]

# Extra calendar window so 20 trading sessions still fit around weekends/holidays.
_OHLCV_PERIOD = "2mo"
_QUOTE_PERIOD = "5d"
_MAX_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 0.5

CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_COOLDOWN_SECONDS = 60
STALE_AFTER_SECONDS = 5 * 60
_EASTERN = ZoneInfo("America/New_York")
_SESSION_OPEN = dt_time(9, 30)
_SESSION_CLOSE = dt_time(16, 0)

# Chart ranges for the stock detail page. 1D falls back to a few sessions of
# intraday bars when the current calendar day has no prints yet (pre-open).
OHLCV_RANGES: dict[str, dict[str, str]] = {
    "1D": {"period": "1d", "interval": "5m", "fallback_period": "5d"},
    "1W": {"period": "5d", "interval": "30m"},
    "1M": {"period": "1mo", "interval": "1d"},
    "3M": {"period": "3mo", "interval": "1d"},
    "1Y": {"period": "1y", "interval": "1d"},
}

# Request-scoped overrides so curl can simulate failure / stale / closed
# without restarting the process (in-memory cache would otherwise be lost).
debug_force_fail: ContextVar[bool] = ContextVar("debug_force_fail", default=False)
debug_force_stale: ContextVar[bool] = ContextVar("debug_force_stale", default=False)
debug_force_market: ContextVar[str | None] = ContextVar("debug_force_market", default=None)


@dataclass
class _Circuit:
    failures: int = 0
    opened_at: datetime | None = None


@dataclass
class _SymbolCache:
    quote: dict[str, Any] | None = None
    quote_fetched_at: datetime | None = None
    ohlcv: list[dict[str, Any]] | None = None
    ohlcv_fetched_at: datetime | None = None
    ranges: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    range_fetched_at: dict[str, datetime] = field(default_factory=dict)


_circuits: dict[str, _Circuit] = {}
_caches: dict[str, _SymbolCache] = {}


def reset_resilience_state() -> None:
    """Clear circuit breakers and last-known caches (tests / local demos)."""
    _circuits.clear()
    _caches.clear()


def set_debug_overrides(
    *,
    force_fail: bool = False,
    force_stale: bool = False,
    force_market: str | None = None,
) -> None:
    debug_force_fail.set(bool(force_fail))
    debug_force_stale.set(bool(force_stale))
    market = force_market.strip().lower() if force_market else None
    if market not in ("open", "closed"):
        market = None
    debug_force_market.set(market)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def us_equity_market_status(now: datetime | None = None) -> MarketStatus:
    """Regular US session: weekdays 9:30am–4:00pm America/New_York (end exclusive)."""
    override = debug_force_market.get() or os.getenv("STOCKLYTIC_FORCE_MARKET_STATUS")
    if override in ("open", "closed"):
        return override  # type: ignore[return-value]

    instant = _aware(now) if now else _now()
    local = instant.astimezone(_EASTERN)
    if local.weekday() >= 5:
        return "closed"
    clock = local.time()
    if _SESSION_OPEN <= clock < _SESSION_CLOSE:
        return "open"
    return "closed"


def freshness_fields(
    fetched_at: datetime | None,
    *,
    from_cache: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """stale / last_updated / market_status for API envelopes.

    `stale` is true when:
    - we are serving circuit-breaker cache, or
    - the US session is open and the payload is older than 5 minutes, or
    - a debug override forces it.
    Last close while the session is shut is not treated as delayed.
    """
    instant = _aware(now) if now else _now()
    status = us_equity_market_status(instant)
    fetched = _aware(fetched_at) if fetched_at else None
    stale = False
    if debug_force_stale.get() or os.getenv("STOCKLYTIC_FORCE_STALE", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        stale = True
    elif from_cache:
        stale = True
    elif status == "open" and fetched is not None:
        age = (instant - fetched).total_seconds()
        threshold = int(os.getenv("STOCKLYTIC_STALE_AFTER_SECONDS", str(STALE_AFTER_SECONDS)))
        stale = age > threshold

    return {
        "stale": stale,
        "last_updated": fetched.isoformat() if fetched else None,
        "market_status": status,
    }


def _cache(symbol: str) -> _SymbolCache:
    ticker = _normalize_symbol(symbol)
    if ticker not in _caches:
        _caches[ticker] = _SymbolCache()
    return _caches[ticker]


def _circuit(symbol: str) -> _Circuit:
    ticker = _normalize_symbol(symbol)
    if ticker not in _circuits:
        _circuits[ticker] = _Circuit()
    return _circuits[ticker]


def _circuit_is_open(symbol: str, now: datetime | None = None) -> bool:
    state = _circuit(symbol)
    if state.failures < CIRCUIT_FAILURE_THRESHOLD or state.opened_at is None:
        return False
    instant = _aware(now) if now else _now()
    elapsed = (instant - _aware(state.opened_at)).total_seconds()
    return elapsed < CIRCUIT_COOLDOWN_SECONDS


def _record_success(symbol: str) -> None:
    _circuits[_normalize_symbol(symbol)] = _Circuit()


def _record_failure(symbol: str, now: datetime | None = None) -> None:
    instant = _aware(now) if now else _now()
    state = _circuit(symbol)
    state.failures += 1
    if state.failures >= CIRCUIT_FAILURE_THRESHOLD:
        state.opened_at = instant


def _provider_forced_down() -> bool:
    if debug_force_fail.get():
        return True
    return os.getenv("STOCKLYTIC_YF_FAIL", "").lower() in {"1", "true", "yes"}


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _with_retry(fn: Callable[[], T], retries: int = _MAX_RETRIES) -> T:
    """Call an external API with exponential backoff (2–3 attempts)."""
    if _provider_forced_down():
        retries = 1
    delay = _INITIAL_BACKOFF_SECONDS
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:  # yfinance raises a mix of network/parse errors
            last_error = exc
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
    assert last_error is not None
    raise last_error


def _history(ticker_symbol: str, **kwargs: Any) -> Any:
    if _provider_forced_down():
        raise RuntimeError("yfinance unavailable (forced failure)")
    return yf.Ticker(ticker_symbol).history(**kwargs)


def _guarded(
    symbol: str,
    loader: Callable[[], T | None],
    read_cache: Callable[[], tuple[T | None, datetime | None]],
    write_cache: Callable[[T], None],
) -> tuple[T | None, dict[str, Any]]:
    """Run `loader` unless the circuit is open; fall back to last-known data.

    Returns (payload, freshness). payload is None when the symbol has no bars
    and nothing is cached. Provider errors raise only when there is no cache.
    """
    ticker = _normalize_symbol(symbol)
    now = _now()

    if _circuit_is_open(ticker, now):
        cached, fetched_at = read_cache()
        if cached is not None:
            return cached, freshness_fields(fetched_at, from_cache=True, now=now)
        raise RuntimeError(
            f"Market data circuit open for {ticker} and no cached payload is available"
        )

    try:
        payload = loader()
    except Exception:
        _record_failure(ticker, now)
        cached, fetched_at = read_cache()
        if cached is not None:
            return cached, freshness_fields(fetched_at, from_cache=True, now=now)
        raise

    if payload is None:
        return None, freshness_fields(None, from_cache=False, now=now)

    _record_success(ticker)
    write_cache(payload)
    _, fetched_at = read_cache()
    return payload, freshness_fields(fetched_at, from_cache=False, now=now)


def fetch_quote(symbol: str) -> dict[str, Any] | None:
    """Return latest price, volume, and % change vs previous close.

    Uses recent daily bars (not `Ticker.info`) so an unknown ticker shows up as
    an empty frame instead of a slow/partial metadata payload.

    Returns None when yfinance has no usable bars (invalid or delisted symbol).
    On repeated provider failures, returns the last cached quote with stale=true.
    """
    ticker_symbol = _normalize_symbol(symbol)
    bucket = _cache(ticker_symbol)

    def loader() -> dict[str, Any] | None:
        return _parse_quote(ticker_symbol)

    def read_cache() -> tuple[dict[str, Any] | None, datetime | None]:
        return bucket.quote, bucket.quote_fetched_at

    def write_cache(payload: dict[str, Any]) -> None:
        bucket.quote = {
            k: v
            for k, v in payload.items()
            if k not in {"stale", "last_updated", "market_status"}
        }
        bucket.quote_fetched_at = _now()

    raw, meta = _guarded(ticker_symbol, loader, read_cache, write_cache)
    if raw is None:
        return None
    core = {k: v for k, v in raw.items() if k not in {"stale", "last_updated", "market_status"}}
    return {**core, **meta}


def _parse_quote(ticker_symbol: str) -> dict[str, Any] | None:
    def _download():
        return _history(ticker_symbol, period=_QUOTE_PERIOD, auto_adjust=True)

    hist = _with_retry(_download)
    if hist is None or hist.empty:
        return None

    hist = hist.dropna(subset=["Close"])
    if hist.empty:
        return None

    last = hist.iloc[-1]
    close = float(last["Close"])
    if close != close:  # NaN
        return None

    volume = last["Volume"]
    volume_int = int(volume) if volume == volume else 0

    previous_close: float | None = None
    change_percent: float | None = None
    if len(hist) >= 2:
        previous_close = float(hist.iloc[-2]["Close"])
        if previous_close:
            change_percent = ((close - previous_close) / previous_close) * 100.0

    as_of = last.name
    as_of_iso = as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of)

    return {
        "symbol": ticker_symbol,
        "price": round(close, 4),
        "volume": volume_int,
        "change_percent": None if change_percent is None else round(change_percent, 4),
        "previous_close": None if previous_close is None else round(previous_close, 4),
        "as_of": as_of_iso,
    }


def fetch_ohlcv(symbol: str, trading_days: int = 20) -> list[dict[str, Any]] | None:
    """Return the last `trading_days` trading sessions of OHLCV for a symbol."""
    bundle = fetch_ohlcv_status(symbol, trading_days=trading_days)
    return bundle["bars"]


def fetch_ohlcv_status(symbol: str, trading_days: int = 20) -> dict[str, Any]:
    """OHLCV bars plus stale / last_updated / market_status."""
    ticker_symbol = _normalize_symbol(symbol)
    bucket = _cache(ticker_symbol)

    def loader() -> list[dict[str, Any]] | None:
        return _parse_ohlcv(ticker_symbol, trading_days)

    def read_cache() -> tuple[list[dict[str, Any]] | None, datetime | None]:
        return bucket.ohlcv, bucket.ohlcv_fetched_at

    def write_cache(payload: list[dict[str, Any]]) -> None:
        bucket.ohlcv = payload
        bucket.ohlcv_fetched_at = _now()

    raw, meta = _guarded(ticker_symbol, loader, read_cache, write_cache)
    return {"bars": raw, **meta}


def _parse_ohlcv(ticker_symbol: str, trading_days: int) -> list[dict[str, Any]] | None:
    def _download():
        return _history(ticker_symbol, period=_OHLCV_PERIOD, auto_adjust=True)

    hist = _with_retry(_download)
    if hist is None or hist.empty:
        return None

    hist = hist.dropna(subset=["Close"]).tail(trading_days)
    if hist.empty:
        return None

    rows: list[dict[str, Any]] = []
    for idx, row in hist.iterrows():
        close = float(row["Close"])
        if close != close:
            continue
        volume = row["Volume"]
        rows.append(
            {
                "date": idx.date().isoformat() if hasattr(idx, "date") else str(idx),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(close, 4),
                "volume": int(volume) if volume == volume else 0,
            }
        )

    return rows or None


def _bar_timestamp(idx: Any) -> tuple[str, str]:
    """Return (iso timestamp, calendar date) for a DatetimeIndex label."""
    iso = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
    if hasattr(idx, "date"):
        return iso, idx.date().isoformat()
    return iso, iso[:10]


def _last_session_only(hist: Any) -> Any:
    idx = hist.index
    if len(idx) == 0:
        return hist
    last = idx[-1]
    last_day = last.date() if hasattr(last, "date") else None
    if last_day is None:
        return hist
    mask = [hasattr(ts, "date") and ts.date() == last_day for ts in idx]
    return hist.loc[mask]


def fetch_ohlcv_range(symbol: str, range_key: str) -> list[dict[str, Any]] | None:
    bundle = fetch_ohlcv_range_status(symbol, range_key)
    return bundle["bars"]


def fetch_ohlcv_range_status(symbol: str, range_key: str) -> dict[str, Any]:
    """OHLCV bars for a chart range plus freshness fields."""
    ticker_symbol = _normalize_symbol(symbol)
    normalized = range_key.strip().upper()
    spec = OHLCV_RANGES.get(normalized)
    if spec is None:
        allowed = ", ".join(OHLCV_RANGES)
        raise ValueError(f"Invalid range '{range_key}'. Use one of: {allowed}")

    bucket = _cache(ticker_symbol)

    def loader() -> list[dict[str, Any]] | None:
        return _parse_ohlcv_range(ticker_symbol, normalized, spec)

    def read_cache() -> tuple[list[dict[str, Any]] | None, datetime | None]:
        return bucket.ranges.get(normalized), bucket.range_fetched_at.get(normalized)

    def write_cache(payload: list[dict[str, Any]]) -> None:
        bucket.ranges[normalized] = payload
        bucket.range_fetched_at[normalized] = _now()

    raw, meta = _guarded(ticker_symbol, loader, read_cache, write_cache)
    return {
        "symbol": ticker_symbol,
        "range": normalized,
        "interval": spec["interval"],
        "bars": raw,
        **meta,
    }


def _parse_ohlcv_range(
    ticker_symbol: str,
    range_key: str,
    spec: dict[str, str],
) -> list[dict[str, Any]] | None:
    interval = spec["interval"]

    def _download(period: str):
        return _history(
            ticker_symbol,
            period=period,
            interval=interval,
            auto_adjust=True,
        )

    hist = _with_retry(lambda: _download(spec["period"]))
    if (hist is None or hist.empty) and spec.get("fallback_period"):
        hist = _with_retry(lambda: _download(spec["fallback_period"]))

    if hist is None or hist.empty:
        return None

    hist = hist.dropna(subset=["Close"])
    if hist.empty:
        return None

    if range_key == "1D":
        hist = _last_session_only(hist)
        if hist.empty:
            return None

    rows: list[dict[str, Any]] = []
    for idx, row in hist.iterrows():
        close = float(row["Close"])
        if close != close:
            continue
        volume = row["Volume"]
        timestamp, date = _bar_timestamp(idx)
        rows.append(
            {
                "timestamp": timestamp,
                "date": date,
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(close, 4),
                "volume": int(volume) if volume == volume else 0,
            }
        )

    return rows or None

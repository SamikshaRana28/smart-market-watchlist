"""Watchlist CRUD and since-last-visit change ranking."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.baseline import get_baseline
from app.core.change_engine import DEFAULT_THRESHOLDS, SENSITIVITY_PRESETS
from app.core.diversification import (
    adds_the_least,
    average_pairwise_correlation,
    build_correlation_matrix,
    closest_pair,
    effective_independent_bets,
    largest_sector,
    lookup_correlation,
    rank_addition_candidates,
    returns_from_closes,
)
from app.core.market_data import (
    fetch_ohlcv,
    fetch_ohlcv_status,
    set_debug_overrides,
    us_equity_market_status,
    market_status_for_symbol,
    currency_for_symbol,
)
from app.core.snapshot_diff import (
    apply_sector_flags,
    build_summary,
    diff_symbol,
    rank_changes,
    select_comparison_snapshot,
)
from app.db import get_db
from app.models import MarketSnapshot, Watchlist, WatchlistItem

DEFAULT_USER_ID = 1


def _thresholds_for(sensitivity: str | None) -> tuple[float, float, float]:
    """Map a sensitivity query param to a threshold preset.

    Falls back to Balanced (the existing 30/60/80 default) for a missing or
    unrecognized value instead of erroring — an invalid param should never
    break the dashboard.
    """
    if not sensitivity:
        return DEFAULT_THRESHOLDS
    return SENSITIVITY_PRESETS.get(sensitivity.strip().lower(), DEFAULT_THRESHOLDS)

# Demo / seed tickers often have an empty WatchlistItem.sector. Fill those so
# calculate_sector_correlation can actually group names on this comparison.
KNOWN_SECTORS = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "JPM": "Financials",
}

# Small, deliberately-curated universe (spans several sectors, not the whole
# tradable market) used to suggest an addition that's least correlated to
# what the user already holds. Keeping this short keeps /diversification fast
# — each new name costs a real OHLCV fetch — while still spanning enough
# sectors for the suggestion to be meaningfully different from the book.
DIVERSIFICATION_CANDIDATES = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM", "V",
    "DIS", "KO", "PEP", "WMT", "XOM", "PFE", "JNJ", "SBUX", "NKE", "IBM",
]
DIVERSIFICATION_TRADING_DAYS = 30

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    user_id: int = DEFAULT_USER_ID
    symbols: list[str] = Field(default_factory=list)


class StockAdd(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    sector: str = ""


class AlertSettingsUpdate(BaseModel):
    enabled: bool
    threshold: float | None = Field(default=None, ge=0, le=100)


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _watchlist_or_404(db: Session, watchlist_id: int) -> Watchlist:
    watchlist = db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(Watchlist.id == watchlist_id)
    ).scalar_one_or_none()
    if watchlist is None:
        raise HTTPException(status_code=404, detail=f"Watchlist {watchlist_id} not found")
    return watchlist


def _recent_snapshots(
    db: Session, user_id: int, symbol: str, limit: int = 2
) -> list[MarketSnapshot]:
    return list(
        db.execute(
            select(MarketSnapshot)
            .where(
                MarketSnapshot.user_id == user_id,
                MarketSnapshot.symbol == symbol,
            )
            .order_by(MarketSnapshot.timestamp.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def _recent_snapshots_bulk(
    db: Session, user_id: int, symbols: list[str], limit: int = 2
) -> dict[str, list[MarketSnapshot]]:
    """Last `limit` snapshots per symbol (most recent first), in one bounded query.

    Uses a ROW_NUMBER() window partitioned by symbol so this stays cheap
    regardless of how much history has piled up — a symbol polled every 45s
    by the frontend's auto-refresh for weeks still costs one indexed lookup
    here, not a full-history fetch for that symbol sliced down in Python.

    Lets GET /watchlists/{id}/changes apply the same "skip a too-fresh
    snapshot" guard the stock-detail route already uses (see
    select_comparison_snapshot). Without this, every call to /changes —
    including a background auto-refresh poll or a quick double-click on
    Refresh — silently resets "since your last visit" to a few seconds
    ago, and every Attention Score collapses toward zero.
    """
    if not symbols:
        return {}

    ranked = (
        select(
            MarketSnapshot.id,
            func.row_number()
            .over(
                partition_by=MarketSnapshot.symbol,
                order_by=MarketSnapshot.timestamp.desc(),
            )
            .label("rn"),
        )
        .where(
            MarketSnapshot.user_id == user_id,
            MarketSnapshot.symbol.in_(symbols),
        )
        .subquery()
    )
    rows = (
        db.execute(
            select(MarketSnapshot)
            .join(ranked, MarketSnapshot.id == ranked.c.id)
            .where(ranked.c.rn <= limit)
            .order_by(MarketSnapshot.symbol, ranked.c.rn)
        )
        .scalars()
        .all()
    )
    grouped: dict[str, list[MarketSnapshot]] = {}
    for row in rows:
        grouped.setdefault(row.symbol, []).append(row)
    return grouped


def _quote_from_bars(symbol: str, bars: list[dict]) -> dict:
    last = bars[-1]
    previous_close = bars[-2]["close"] if len(bars) >= 2 else None
    return {
        "symbol": symbol,
        "price": last["close"],
        "volume": last.get("volume") or 0,
        "high": last.get("high"),
        "low": last.get("low"),
        "previous_close": previous_close,
        "as_of": last.get("date"),
    }


def _triggered_alerts(watchlist: Watchlist, ranked: list[dict]) -> list[str]:
    """Symbols whose Attention Score meets/exceeds this watchlist's Alert
    Threshold on this comparison. Empty whenever alerts are off or no
    threshold is set — App.jsx only fires a browser Notification for
    symbols in this list, so returning [] here means "stay silent".
    """
    if not watchlist.alerts_enabled or watchlist.alert_threshold is None:
        return []
    return [
        row["symbol"]
        for row in ranked
        if row.get("status") == "compared"
        and row.get("attention_score") is not None
        and row["attention_score"] >= watchlist.alert_threshold
    ]


def _snapshot_payload(row: MarketSnapshot) -> dict:
    ts = row.timestamp
    return {
        "price": row.price,
        "volume": row.volume,
        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
    }


@router.post("")
def create_watchlist(body: WatchlistCreate, db: Session = Depends(get_db)):
    watchlist = Watchlist(user_id=body.user_id, name=body.name.strip())
    db.add(watchlist)
    db.flush()
    seen: set[str] = set()
    for raw in body.symbols:
        symbol = _normalize_symbol(raw)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        db.add(
            WatchlistItem(
                watchlist_id=watchlist.id,
                symbol=symbol,
                sector=KNOWN_SECTORS.get(symbol, ""),
            )
        )
    db.commit()
    db.refresh(watchlist)
    return _serialize_watchlist(watchlist)


@router.get("")
def list_watchlists(user_id: int = DEFAULT_USER_ID, db: Session = Depends(get_db)):
    rows = db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(Watchlist.user_id == user_id)
        .order_by(Watchlist.id)
    ).scalars().all()
    return [_serialize_watchlist(row) for row in rows]


@router.patch("/{watchlist_id}/alert-settings")
def update_alert_settings(
    watchlist_id: int, body: AlertSettingsUpdate, db: Session = Depends(get_db)
):
    """Persist the watchlist-level Alert Threshold (see Watchlist.alerts_enabled).

    `threshold` may be omitted/null — e.g. the toggle is being switched off
    without touching whatever number was last entered. Notification.requestPermission()
    happens client-side in AlertSettings.jsx before this is ever called, so this
    endpoint only owns the stored preference, not the browser permission itself.
    """
    watchlist = _watchlist_or_404(db, watchlist_id)
    watchlist.alerts_enabled = body.enabled
    watchlist.alert_threshold = body.threshold
    db.commit()
    db.refresh(watchlist)
    return _serialize_watchlist(watchlist)


@router.post("/{watchlist_id}/stocks")
def add_stock(watchlist_id: int, body: StockAdd, db: Session = Depends(get_db)):
    watchlist = _watchlist_or_404(db, watchlist_id)
    symbol = _normalize_symbol(body.symbol)
    existing = {item.symbol for item in watchlist.items}
    if symbol in existing:
        raise HTTPException(status_code=409, detail=f"{symbol} is already on this watchlist")
    item = WatchlistItem(
        watchlist_id=watchlist.id,
        symbol=symbol,
        sector=body.sector.strip() or KNOWN_SECTORS.get(symbol, ""),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "symbol": item.symbol, "sector": item.sector}


@router.delete("/{watchlist_id}/stocks/{symbol}")
def remove_stock(watchlist_id: int, symbol: str, db: Session = Depends(get_db)):
    watchlist = _watchlist_or_404(db, watchlist_id)
    ticker = _normalize_symbol(symbol)
    item = next((row for row in watchlist.items if row.symbol == ticker), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{ticker} is not on this watchlist")
    db.delete(item)
    db.commit()
    return {"removed": ticker}


@router.get("/{watchlist_id}/stocks/{symbol}")
def get_stock_detail(
    watchlist_id: int,
    symbol: str,
    db: Session = Depends(get_db),
    force_fail: bool = Query(False),
    force_stale: bool = Query(False),
    force_market: str | None = Query(None),
):
    """Signals + last-visit delta for one name. Does not write a new snapshot."""
    set_debug_overrides(
        force_fail=force_fail,
        force_stale=force_stale,
        force_market=force_market,
    )
    watchlist = _watchlist_or_404(db, watchlist_id)
    ticker = _normalize_symbol(symbol)
    item = next((row for row in watchlist.items if row.symbol == ticker), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{ticker} is not on this watchlist")

    bundle = fetch_ohlcv_status(ticker)
    bars = bundle.get("bars")
    quote = _quote_from_bars(ticker, bars) if bars else None
    baseline = get_baseline(ticker, bars=bars) if bars else None

    snapshot_rows = _recent_snapshots(db, watchlist.user_id, ticker)
    payloads = [_snapshot_payload(row) for row in snapshot_rows]
    prior = select_comparison_snapshot(payloads, now=datetime.now(timezone.utc))

    change = diff_symbol(
        ticker,
        sector=(item.sector or "").strip() or KNOWN_SECTORS.get(ticker, ""),
        snapshot=prior,
        quote=quote,
        baseline=baseline,
        current_bar=bars[-1] if bars else None,
    )
    change["stale"] = bundle["stale"]
    change["last_updated"] = bundle["last_updated"]
    change["market_status"] = bundle["market_status"]
    change["currency"] = bundle.get("currency", currency_for_symbol(symbol))

    return {
        "watchlist_id": watchlist.id,
        "user_id": watchlist.user_id,
        "last_viewed_at": (
            watchlist.last_viewed_at.isoformat() if watchlist.last_viewed_at else None
        ),
        "stale": bundle["stale"],
        "last_updated": bundle["last_updated"],
        "market_status": bundle["market_status"],
        "change": change,
    }


# How the dominant-reason badge (🔊 volume spike / 📈 breakout / etc.) picks
# its label — a fixed keyword→condition lookup, not a trained model. Surfaced
# on the Feed panel so the "why" behind headlines is as auditable as the
# Attention Score math itself.
HEADLINE_MODEL = "rule-based lexicon"
# Matches the 45s interval App.jsx actually polls /changes at — kept as one
# constant so the Feed panel can't drift out of sync with the real behavior.
POLLING_INTERVAL_SECONDS = 45


@router.get("/{watchlist_id}/changes")
def get_watchlist_changes(
    watchlist_id: int,
    db: Session = Depends(get_db),
    force_fail: bool = Query(False),
    force_stale: bool = Query(False),
    force_market: str | None = Query(None),
    force_disagree: bool = Query(False),
    sensitivity: str | None = Query(None),
):
    """Compare last snapshots to live data and return Attention Scores, ranked.

    First time a symbol is seen for this user it is tagged `tracking_started_today`
    instead of scoring a fake move from an empty baseline. A new snapshot is stored
    after the comparison so the next visit has a real prior price/volume.

    `sensitivity` (conservative | balanced | aggressive) shifts the
    classify_attention cutoffs; missing or invalid values fall back to balanced.
    """
    cycle_started = time.perf_counter()
    set_debug_overrides(
        force_fail=force_fail,
        force_stale=force_stale,
        force_market=force_market,
        force_disagree=force_disagree,
    )
    thresholds = _thresholds_for(sensitivity)
    watchlist = _watchlist_or_404(db, watchlist_id)
    items = list(watchlist.items)
    symbols = [item.symbol for item in items]
    sector_by_symbol = {
        item.symbol: (item.sector or "").strip() or KNOWN_SECTORS.get(item.symbol, "")
        for item in items
    }

    snapshots = _recent_snapshots_bulk(db, watchlist.user_id, symbols)

    rows: list[dict] = []
    now = datetime.now(timezone.utc)
    bars_fetched = 0
    applied = 0
    rejected = 0

    for symbol in symbols:
        try:
            bundle = fetch_ohlcv_status(symbol)
        except Exception:
            # Total outage (circuit open, nothing cached yet for a brand-new
            # symbol): degrade this one row to "no data" instead of failing
            # the whole dashboard load — the same resilience story as a
            # stale/cached fallback, just with nothing to fall back to.
            bundle = {
                "bars": None,
                "stale": True,
                "last_updated": None,
                "market_status": market_status_for_symbol(symbol, now),
                "currency": currency_for_symbol(symbol),
                "sources_disagree": False,
            }
        bars = bundle.get("bars")
        quote = _quote_from_bars(symbol, bars) if bars else None
        baseline = get_baseline(symbol, bars=bars) if bars else None
        payloads = [_snapshot_payload(row) for row in snapshots.get(symbol, [])]
        prior = select_comparison_snapshot(payloads, now=now)
        row = diff_symbol(
            symbol,
            sector=sector_by_symbol.get(symbol, ""),
            snapshot=prior,
            quote=quote,
            baseline=baseline,
            current_bar=bars[-1] if bars else None,
            thresholds=thresholds,
        )
        row["stale"] = bundle["stale"]
        row["last_updated"] = bundle["last_updated"]
        row["market_status"] = bundle["market_status"]
        row["currency"] = bundle.get("currency", currency_for_symbol(symbol))
        row["sources_disagree"] = bundle.get("sources_disagree", False)
        rows.append(row)

        if quote is not None:
            applied += 1
            bars_fetched += len(bars or [])
            db.add(
                MarketSnapshot(
                    user_id=watchlist.user_id,
                    symbol=symbol,
                    price=float(quote["price"]),
                    volume=int(quote["volume"]),
                    timestamp=now,
                )
            )
        else:
            rejected += 1

    ranked = rank_changes(apply_sector_flags(rows))
    previous_viewed = watchlist.last_viewed_at
    summary = build_summary(ranked, previous_viewed=previous_viewed, now=now)
    watchlist.last_viewed_at = now
    db.commit()

    stored_signals = (
        db.query(MarketSnapshot).filter(MarketSnapshot.user_id == watchlist.user_id).count()
    )
    any_stale = any(bool(row.get("stale")) for row in ranked)
    any_disagree = any(bool(row.get("sources_disagree")) for row in ranked)
    if force_fail or rejected > 0 and applied == 0 and symbols:
        feed_status = "outage"
    elif any_disagree:
        feed_status = "disagree"
    elif any_stale:
        feed_status = "stale"
    else:
        feed_status = "healthy"

    return {
        "watchlist_id": watchlist.id,
        "user_id": watchlist.user_id,
        "last_viewed_at": previous_viewed.isoformat() if previous_viewed else None,
        "viewed_at": now.isoformat(),
        "summary": summary,
        "stale": any_stale,
        "last_updated": max(
            (row["last_updated"] for row in ranked if row.get("last_updated")),
            default=None,
        ),
        "market_status": us_equity_market_status(now),
        "sensitivity": (
            sensitivity.strip().lower()
            if sensitivity and sensitivity.strip().lower() in SENSITIVITY_PRESETS
            else "balanced"
        ),
        "alerts_enabled": watchlist.alerts_enabled,
        "alert_threshold": watchlist.alert_threshold,
        "triggered_alerts": _triggered_alerts(watchlist, ranked),
        "changes": ranked,
        "feed": {
            "status": feed_status,
            "sources_disagree": any_disagree,
            "polling_interval_seconds": POLLING_INTERVAL_SECONDS,
            "cycle_time_ms": round((time.perf_counter() - cycle_started) * 1000),
            "applied": applied,
            "rejected": rejected,
            "headline_model": HEADLINE_MODEL,
            "stored_signals": stored_signals,
            "bars_fetched": bars_fetched,
        },
    }


@router.get("/{watchlist_id}/diversification")
def get_watchlist_diversification(watchlist_id: int, db: Session = Depends(get_db)):
    """Portfolio-shape metrics: pairwise correlation, effective independent
    bets, the most-redundant pair, the least-redundant holding, the largest
    sector, and a couple of not-yet-held names that would diversify the book
    the most if added.

    Correlation is computed from `DIVERSIFICATION_TRADING_DAYS` of daily
    returns, so it needs at least a couple of priced symbols to say anything;
    a 0- or 1-name watchlist gets a minimal, honest response instead of a
    fabricated score.
    """
    watchlist = _watchlist_or_404(db, watchlist_id)
    items = list(watchlist.items)
    symbols = [item.symbol for item in items]
    sector_by_symbol = {
        item.symbol: (item.sector or "").strip() or KNOWN_SECTORS.get(item.symbol, "")
        for item in items
    }
    sector = largest_sector(sector_by_symbol)
    sector_payload = None if sector is None else {"sector": sector[0], "pct": round(sector[1], 1)}

    if len(symbols) < 2:
        return {
            "watchlist_id": watchlist.id,
            "n": len(symbols),
            "independent_bets": float(len(symbols)),
            "avg_pair_correlation": None,
            "closest_pair": None,
            "adds_least": None,
            "largest_sector": sector_payload,
            "matrix": {"symbols": symbols, "values": [[1.0]] if symbols else []},
            "suggestions": [],
            "insufficient_data": True,
        }

    returns_by_symbol: dict[str, list[float]] = {}
    for symbol in symbols:
        bars = fetch_ohlcv(symbol, trading_days=DIVERSIFICATION_TRADING_DAYS)
        if bars:
            closes = [bar["close"] for bar in bars]
            returns = returns_from_closes(closes)
            if returns:
                returns_by_symbol[symbol] = returns

    matrix = build_correlation_matrix(returns_by_symbol)
    avg_corr = average_pairwise_correlation(matrix)
    bets = effective_independent_bets(len(symbols), avg_corr)
    pair = closest_pair(matrix)
    least = adds_the_least(symbols, matrix)

    candidate_returns: dict[str, list[float]] = {}
    for symbol in DIVERSIFICATION_CANDIDATES:
        if symbol in returns_by_symbol:
            continue
        bars = fetch_ohlcv(symbol, trading_days=DIVERSIFICATION_TRADING_DAYS)
        if bars:
            closes = [bar["close"] for bar in bars]
            returns = returns_from_closes(closes)
            if returns:
                candidate_returns[symbol] = returns

    suggestions = rank_addition_candidates(candidate_returns, returns_by_symbol, limit=3)

    grid = [
        [lookup_correlation(a, b, matrix) for b in symbols]
        for a in symbols
    ]

    return {
        "watchlist_id": watchlist.id,
        "n": len(symbols),
        "independent_bets": round(bets, 2),
        "avg_pair_correlation": None if avg_corr is None else round(avg_corr, 2),
        "closest_pair": (
            None if pair is None else {**pair, "correlation": round(pair["correlation"], 2)}
        ),
        "adds_least": (
            None if least is None else {"symbol": least[0], "avg_correlation": round(least[1], 2)}
        ),
        "largest_sector": sector_payload,
        "matrix": {"symbols": symbols, "values": grid},
        "suggestions": [
            {"symbol": row["symbol"], "avg_correlation": round(row["avg_correlation"], 2)}
            for row in suggestions
        ],
    }


def _serialize_watchlist(watchlist: Watchlist) -> dict:
    return {
        "id": watchlist.id,
        "user_id": watchlist.user_id,
        "name": watchlist.name,
        "last_viewed_at": (
            watchlist.last_viewed_at.isoformat() if watchlist.last_viewed_at else None
        ),
        "alerts_enabled": watchlist.alerts_enabled,
        "alert_threshold": watchlist.alert_threshold,
        "symbols": [
            {
                "symbol": item.symbol,
                "sector": (item.sector or "").strip() or KNOWN_SECTORS.get(item.symbol, ""),
            }
            for item in sorted(watchlist.items, key=lambda row: row.symbol)
        ],
    }

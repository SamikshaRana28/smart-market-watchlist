"""Watchlist CRUD and since-last-visit change ranking."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.baseline import get_baseline
from app.core.change_engine import DEFAULT_THRESHOLDS, SENSITIVITY_PRESETS
from app.core.market_data import fetch_ohlcv_status, set_debug_overrides, us_equity_market_status
from app.core.snapshot_diff import (
    apply_sector_flags,
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

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    user_id: int = DEFAULT_USER_ID
    symbols: list[str] = Field(default_factory=list)


class StockAdd(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    sector: str = ""


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


def _latest_snapshots(
    db: Session, user_id: int, symbols: list[str]
) -> dict[str, MarketSnapshot]:
    if not symbols:
        return {}

    latest = (
        select(
            MarketSnapshot.symbol,
            func.max(MarketSnapshot.timestamp).label("max_ts"),
        )
        .where(
            MarketSnapshot.user_id == user_id,
            MarketSnapshot.symbol.in_(symbols),
        )
        .group_by(MarketSnapshot.symbol)
        .subquery()
    )
    rows = db.execute(
        select(MarketSnapshot).join(
            latest,
            (MarketSnapshot.user_id == user_id)
            & (MarketSnapshot.symbol == latest.c.symbol)
            & (MarketSnapshot.timestamp == latest.c.max_ts),
        )
    ).scalars().all()
    return {row.symbol: row for row in rows}


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


@router.get("/{watchlist_id}/changes")
def get_watchlist_changes(
    watchlist_id: int,
    db: Session = Depends(get_db),
    force_fail: bool = Query(False),
    force_stale: bool = Query(False),
    force_market: str | None = Query(None),
    sensitivity: str | None = Query(None),
):
    """Compare last snapshots to live data and return Attention Scores, ranked.

    First time a symbol is seen for this user it is tagged `tracking_started_today`
    instead of scoring a fake move from an empty baseline. A new snapshot is stored
    after the comparison so the next visit has a real prior price/volume.

    `sensitivity` (conservative | balanced | aggressive) shifts the
    classify_attention cutoffs; missing or invalid values fall back to balanced.
    """
    set_debug_overrides(
        force_fail=force_fail,
        force_stale=force_stale,
        force_market=force_market,
    )
    thresholds = _thresholds_for(sensitivity)
    watchlist = _watchlist_or_404(db, watchlist_id)
    items = list(watchlist.items)
    symbols = [item.symbol for item in items]
    sector_by_symbol = {
        item.symbol: (item.sector or "").strip() or KNOWN_SECTORS.get(item.symbol, "")
        for item in items
    }

    snapshots = _latest_snapshots(db, watchlist.user_id, symbols)

    rows: list[dict] = []
    now = datetime.now(timezone.utc)

    for symbol in symbols:
        bundle = fetch_ohlcv_status(symbol)
        bars = bundle.get("bars")
        quote = _quote_from_bars(symbol, bars) if bars else None
        baseline = get_baseline(symbol, bars=bars) if bars else None
        prior = snapshots.get(symbol)
        row = diff_symbol(
            symbol,
            sector=sector_by_symbol.get(symbol, ""),
            snapshot=None if prior is None else _snapshot_payload(prior),
            quote=quote,
            baseline=baseline,
            current_bar=bars[-1] if bars else None,
            thresholds=thresholds,
        )
        row["stale"] = bundle["stale"]
        row["last_updated"] = bundle["last_updated"]
        row["market_status"] = bundle["market_status"]
        rows.append(row)

        if quote is not None:
            db.add(
                MarketSnapshot(
                    user_id=watchlist.user_id,
                    symbol=symbol,
                    price=float(quote["price"]),
                    volume=int(quote["volume"]),
                    timestamp=now,
                )
            )

    ranked = rank_changes(apply_sector_flags(rows))
    previous_viewed = watchlist.last_viewed_at
    watchlist.last_viewed_at = now
    db.commit()

    return {
        "watchlist_id": watchlist.id,
        "user_id": watchlist.user_id,
        "last_viewed_at": previous_viewed.isoformat() if previous_viewed else None,
        "viewed_at": now.isoformat(),
        "stale": any(bool(row.get("stale")) for row in ranked),
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
        "changes": ranked,
    }


def _serialize_watchlist(watchlist: Watchlist) -> dict:
    return {
        "id": watchlist.id,
        "user_id": watchlist.user_id,
        "name": watchlist.name,
        "last_viewed_at": (
            watchlist.last_viewed_at.isoformat() if watchlist.last_viewed_at else None
        ),
        "symbols": [
            {
                "symbol": item.symbol,
                "sector": (item.sector or "").strip() or KNOWN_SECTORS.get(item.symbol, ""),
            }
            for item in sorted(watchlist.items, key=lambda row: row.symbol)
        ],
    }

"""Market-data routes: current quote and OHLCV for a symbol via yfinance."""

from fastapi import APIRouter, HTTPException, Query

from app.core.market_data import (
    OHLCV_RANGES,
    fetch_ohlcv_range_status,
    fetch_quote,
    set_debug_overrides,
)

router = APIRouter(prefix="/market", tags=["market"])


def _apply_debug(
    force_fail: bool,
    force_stale: bool,
    force_market: str | None,
) -> None:
    set_debug_overrides(
        force_fail=force_fail,
        force_stale=force_stale,
        force_market=force_market,
    )


@router.get("/{symbol}/ohlcv")
def get_market_ohlcv(
    symbol: str,
    range: str = Query("1M", description="Chart window: 1D, 1W, 1M, 3M, or 1Y"),
    force_fail: bool = Query(False, description="Simulate provider failure (circuit breaker)"),
    force_stale: bool = Query(False, description="Mark payload as delayed"),
    force_market: str | None = Query(None, description="Override market_status: open|closed"),
):
    """Candlestick/line series for the stock detail page."""
    _apply_debug(force_fail, force_stale, force_market)
    try:
        bundle = fetch_ohlcv_range_status(symbol, range)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Market data provider failed: {exc}",
        ) from exc

    if bundle.get("bars") is None:
        raise HTTPException(
            status_code=404,
            detail=f"No market data found for symbol '{symbol.strip().upper()}'",
        )

    normalized = range.strip().upper()
    return {
        **bundle,
        "interval": bundle.get("interval") or OHLCV_RANGES[normalized]["interval"],
    }


@router.get("/{symbol}")
def get_market_quote(
    symbol: str,
    force_fail: bool = Query(False, description="Simulate provider failure (circuit breaker)"),
    force_stale: bool = Query(False, description="Mark payload as delayed"),
    force_market: str | None = Query(None, description="Override market_status: open|closed"),
):
    """Fetch current price, volume, and day % change for `symbol`.

    404 when yfinance returns no bars (unknown/invalid ticker).
    """
    _apply_debug(force_fail, force_stale, force_market)
    try:
        quote = fetch_quote(symbol)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Market data provider failed: {exc}",
        ) from exc

    if quote is None:
        raise HTTPException(
            status_code=404,
            detail=f"No market data found for symbol '{symbol.strip().upper()}'",
        )

    return quote

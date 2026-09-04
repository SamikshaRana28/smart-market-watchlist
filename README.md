# Stocklytic — Smart Market Watchlist

*Built for Code 2026 — "Build a smart market watchlist"*

A watchlist that doesn't just show stock prices — it tells you **what's
actually worth your attention since you last checked**, using
volatility-normalized statistical significance instead of a flat
"stock moved X%" threshold.

## Why this approach

We use **explainable statistical anomaly detection** (Z-score + volume +
volatility, blended into a single 0–100 Attention Score) instead of a
black-box ML prediction model. The goal is to detect *meaningful change*
since the user's last visit, not to predict future prices — a
statistically-grounded, auditable score does that better than a model
whose reasoning can't be explained on demand.

## Core features

- **Watchlist CRUD** — create a watchlist, add/remove symbols, duplicates
  blocked at the database level
- **Real market data** — live quotes and historical OHLCV via `yfinance`
  (free tier; data can run ~15 min behind the live tape — see
  *Known limitations* below)
- **Attention Score engine** — `0.35×price + 0.30×z_score + 0.20×volume +
  0.15×volatility`, bucketed into Normal / Moderate / Important /
  Significant
- **Snapshot-based "what changed since last visit"** — every dashboard
  load is diffed against the last stored snapshot, not against a fixed
  time window. First-ever view of a symbol is labeled
  `tracking_started_today` instead of faking a 0% comparison
- **Sector correlation flagging** — when 2+ same-sector stocks move
  unusually on the same comparison, they're flagged
  `sector_correlation` (a sector-wide move) instead of
  `stock_specific`, with a dashboard banner
- **Sensitivity presets** — Conservative / Balanced / Aggressive shift the
  classification thresholds live from the dashboard:
  | Preset | Moderate | Important | Significant |
  |---|---|---|---|
  | Conservative | 40 | 65 | 85 |
  | Balanced (default) | 30 | 60 | 80 |
  | Aggressive | 20 | 45 | 70 |
- **Resilience layer** — circuit breaker (3 consecutive provider failures
  → serve cache for 60s), stale-data detection (>5 min old during market
  hours), and automatic market-closed detection, all surfaced as UI
  badges ("Last traded" / "Data delayed") instead of silently showing
  wrong numbers
- **Digest mode** — if the user hasn't visited in 3+ days, the dashboard
  shows a rolled-up summary instead of flooding them with every stock
  individually
- **Context badges** — 🔊 volume spike / 📈 breakout / 📊 volatility /
  🔗 sector correlation icons next to each row's explanation, so the
  *why* is scannable at a glance, not just readable

## Stack

- **Frontend:** React (Vite) + Tailwind + Recharts
- **Backend:** FastAPI (Python)
- **Database:** SQLite for local dev (swappable to Postgres later —
  models are already ORM-based via SQLAlchemy, so this is a config
  change, not a rewrite)
- **Cache:** Redis for the 24h rolling baseline (mean return, std dev,
  avg volume, avg volatility); falls back gracefully to a live
  computation if Redis isn't running
- **Market data:** yfinance

## Project structure

```
backend/
  main.py                    # FastAPI entrypoint
  requirements.txt
  stocklytic.db               # SQLite file (created on first run, gitignored)
  app/
    core/
      change_engine.py       # Attention Score math, sector correlation, sensitivity presets
      snapshot_diff.py       # snapshot vs current → per-row change + summary
      baseline.py            # 24h rolling baseline (Redis-cached)
      market_data.py         # yfinance wrapper: retries, circuit breaker, stale/closed detection
    models/                  # SQLAlchemy models (Watchlist, WatchlistItem, MarketSnapshot)
    routes/
      watchlists.py          # CRUD + /changes (the core endpoint)
      market.py               # /market/{symbol}, /market/{symbol}/ohlcv
  tests/                     # 48 unit tests, no DB/network required

frontend/
  src/
    App.jsx                  # dashboard shell, sensitivity toggle, refresh
    api.js                   # backend calls incl. force_fail/force_stale/force_market test params
    format.js                # shared formatting + "what's the dominant reason" logic
    components/
      Hero.jsx               # headline + digest summary line
      ChangeCard.jsx          # ranked card view with context badges
      WatchlistTable.jsx      # full sortable table with context badges
      AddStockForm.jsx
      DataStatusBadge.jsx      # "Last traded" / "Data delayed" badge
      PriceChart.jsx
    pages/
      StockDetail.jsx          # per-symbol page: chart, range toggle, "why it matters"

docs/
  roadmap.md                 # phase-by-phase build log
```

## Running locally

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```
Runs at `http://127.0.0.1:8000`. Interactive API docs at `/docs`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Runs at whatever port Vite prints (usually `http://localhost:5173`).

Redis is optional for local dev — if it isn't running, baseline
computation just runs live instead of reading from cache. No setup
required to demo.

## Testing

### Backend (48 tests, no DB or network needed)
```bash
cd backend
python -m unittest discover tests -v
```

### Manual end-to-end checklist
See `docs/roadmap.md` for the full manual QA checklist (watchlist
lifecycle, resilience via `force_fail`/`force_stale`/`force_market` query
params, sensitivity toggle, digest mode, sector correlation, mobile
responsiveness).

## Known limitations (by design, not oversight)

- **Data is not tick-by-tick real-time.** `yfinance`'s free tier is
  typically ~15 minutes delayed during market hours. The app is honest
  about this via `stale` and `market_status` fields rather than
  pretending to be a live terminal.
- **No auth yet.** Single hardcoded `user_id=1` for the demo — the
  schema is already multi-user shaped (`user_id` on every watchlist), so
  adding JWT auth is additive, not a redesign.
- **Sector is user-entered**, not pulled from a reference dataset —
  fine for a hackathon demo; a production version would resolve sector
  from a symbol-metadata provider instead of trusting free-text input.

## Possible next steps

- Multiple watchlists per user (switcher/dropdown — schema already
  supports it, just needs a UI selector)
- Symbol search/autocomplete when adding a stock, instead of typing the
  exact ticker
- Price/score alert thresholds (notify when a symbol crosses a chosen
  Attention Score)
- Swap SQLite → Postgres + add a second market-data provider as a
  fallback for true multi-user scale

## Roadmap

See `docs/roadmap.md` for the full phase-by-phase build log.
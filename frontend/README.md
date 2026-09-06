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
  (free tier; data can run behind the live tape — see
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
- **Portfolio diversification panel** — a pairwise return-correlation
  matrix across every symbol in the watchlist, an "effective independent
  bets" score (how concentrated the list actually is, not just how many
  names are on it), the single closest-correlated pair, and "least
  correlated to add" suggestions. Undefined correlation (too little
  overlap, or a symbol with zero variance) returns `None` rather than a
  fake `0`
- **Feed transparency panel** — every `/changes` response reports how
  many symbols' data was applied vs rejected this cycle, the cycle time,
  and an overall feed status (`healthy` / `stale` / `disagree` /
  `outage`), so the resilience layer is visible in the UI, not just
  logged server-side
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
- **Multiple watchlists per user** — switcher in the header, persisted
  via `?watchlist=` in the URL and localStorage so it survives a reload
- **Symbol search/autocomplete** — type a ticker or a company name (e.g.
  "google") when adding a stock; matches a curated name list plus a live
  `yfinance` lookup, so you don't need to already know the exact ticker
- **NSE (India) support alongside US markets** — add a `.NS`/`.BO` ticker
  (e.g. `TCS.NS`, `RELIANCE.NS` — 20 common NSE names are in the curated
  autocomplete list) and it's priced in ₹ and judged against NSE trading
  hours (9:15am–3:30pm IST), while a US ticker in the *same* watchlist
  stays in $ on US hours (9:30am–4pm ET) — each symbol is evaluated on
  its own exchange's clock and currency, not one assumed for everything
- **Attention Score alerts** — per-watchlist threshold, persisted server-side
  (`Watchlist.alerts_enabled` / `alert_threshold`); when a symbol's score
  crosses it on a visit, a browser notification fires (Notification API,
  foreground only — no server-side push)
- **Score Accuracy Tracker (self-audit)** — every symbol flagged Moderate,
  Important, or Significant is recorded with its price at that moment.
  `EVALUATION_WINDOW_DAYS` (3) later, `/watchlists/accuracy` checks whether
  the price actually moved ≥3% further and reports an aggregate hit rate,
  broken down by label — the app grading its own signal against real
  outcomes instead of just asserting significance and moving on. Deduped to
  one flagged event per symbol per calendar day so the 45s auto-refresh
  doesn't spam duplicate rows for the same flag

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
      market_data.py         # yfinance wrapper: retries, circuit breaker, stale/closed detection, symbol search
      diversification.py     # pairwise correlation matrix, independent-bets score, closest pair
      accuracy.py             # Score Accuracy Tracker: evaluation window, hit-rate summary
    models/                  # SQLAlchemy models (Watchlist, WatchlistItem, MarketSnapshot, FlaggedEvent)
    routes/
      watchlists.py          # CRUD + /changes (core endpoint) + alert-settings + feed status + /accuracy + /diversification
      market.py               # /market/{symbol}, /market/{symbol}/ohlcv, /market/search
  tests/                     # 121 unit tests — 118 pure-logic (no DB/network); 3 route-level
                              # tests in test_feed_status.py use a throwaway SQLite file via
                              # FastAPI's TestClient (no live network calls; yfinance is mocked)

frontend/
  .env.example               # optional VITE_API_URL override (defaults to 127.0.0.1:8000)
  src/
    App.jsx                  # dashboard shell, sensitivity toggle, refresh
    api.js                   # backend calls incl. force_fail/force_stale/force_market test params
    format.js                # shared formatting + "what's the dominant reason" logic
    components/
      Hero.jsx               # headline + digest summary line
      ChangeCard.jsx          # ranked card view with context badges
      WatchlistTable.jsx      # full sortable table with context badges
      WatchlistSwitcher.jsx    # multi-watchlist tabs + "new watchlist" form
      AddStockForm.jsx
      SymbolAutocomplete.jsx   # ticker/company-name search dropdown
      AlertSettings.jsx        # Attention Score alert threshold + browser notifications
      DiversificationPanel.jsx # correlation matrix + independent-bets score
      AccuracyPanel.jsx        # Score Accuracy Tracker: hit rate, by-label breakdown
      FeedPanel.jsx            # feed health status, applied/rejected counts, cycle time
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
`VITE_API_URL` is optional — see `.env.example` — the app defaults to
`http://127.0.0.1:8000` if it isn't set.

Redis is optional for local dev — if it isn't running, baseline
computation just runs live instead of reading from cache. No setup
required to demo.

## Testing

### Backend (121 tests)
```bash
cd backend
python -m unittest discover tests -v
```
118 of these are pure-logic tests (`change_engine`, `snapshot_diff`,
`diversification`, `accuracy`, `market_data` helpers, etc.) — no DB, no
network, run in milliseconds. The remaining 3, in `test_feed_status.py`,
are route-level tests: they spin up a throwaway SQLite file (never the
real dev `stocklytic.db`) behind a real FastAPI `TestClient` to exercise
the `/changes` endpoint end-to-end, including the "total outage with
nothing cached" path. `fetch_ohlcv_status` is mocked there too, so no
test in the suite makes a real network call.

### Manual end-to-end checklist
See `docs/roadmap.md` for the full manual QA checklist (watchlist
lifecycle, resilience via `force_fail`/`force_stale`/`force_market` query
params, sensitivity toggle, digest mode, sector correlation, diversification
panel, feed status, mobile responsiveness).

## Known limitations (by design, not oversight)

- **Data is not tick-by-tick real-time.** `yfinance`'s free tier can run
  behind the live tape during market hours. The app is honest about this
  via `stale` and `market_status` fields rather than pretending to be a
  live terminal.
- **No auth yet.** Single hardcoded `user_id=1` for the demo — the
  schema is already multi-user shaped (`user_id` on every watchlist), so
  adding JWT auth is additive, not a redesign.
- **Sector is user-entered**, not pulled from a reference dataset —
  fine for a hackathon demo; a production version would resolve sector
  from a symbol-metadata provider instead of trusting free-text input.
- **Alerts are foreground-only.** The Notification API only fires while
  the tab is open — a threshold crossing while the tab is closed is
  missed. The threshold itself is still persisted server-side per
  watchlist, so this is a delivery-channel limitation, not a data one.
- **Correlation needs history.** `diversification.py` returns `None` for
  a pair without enough overlapping return data (or zero variance)
  rather than a misleading `0` — so a very new symbol may not show a
  correlation figure yet.
- **The accuracy evaluation window (3 days) is short** for a genuinely
  robust significance test — it was picked so the self-audit produces
  real hit-rate numbers within a normal demo/review timeframe rather than
  requiring weeks of flagged history first. A production version would
  likely use a longer window (and possibly several windows per flag) for
  a more statistically meaningful hit rate.

## Possible next steps

- Swap SQLite → Postgres + add a second market-data provider as a
  fallback for true multi-user scale
- Real auth (JWT) — schema is already multi-user shaped (`user_id` on
  every watchlist), so this is additive, not a redesign
- Sector resolved from a symbol-metadata provider instead of user-entered
  free text
- Server-side alerting (email/SMS/push) instead of foreground-only
  browser notifications, so a threshold crossing is caught even when the
  tab isn't open

## Roadmap

See `docs/roadmap.md` for the full phase-by-phase build log.

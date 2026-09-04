# Smart Market Watchlist

A watchlist that doesn't just show stock prices — it tells you what's actually
worth your attention since you last checked, using volatility-normalized
statistical significance instead of flat % thresholds.

## Why this approach
We use explainable statistical anomaly detection (Z-score + volume + volatility)
instead of a black-box ML prediction model, because the goal is to detect
*meaningful change*, not predict future prices.

## Stack
- **Frontend:** React (Vite) + Tailwind + Recharts
- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL
- **Cache:** Redis
- **Market Data:** yfinance (primary), Finnhub (backup)

## Project structure
```
backend/
  main.py              # FastAPI entrypoint
  requirements.txt
  app/
    core/
      change_engine.py # the meaningful-change / attention score algorithm
    models/            # DB models
    routes/            # API routes
frontend/
  (Vite React app)
```

## Running locally

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Roadmap
See `docs/roadmap.md` for the full phase-by-phase build plan.

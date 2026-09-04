# Smart Market Watchlist — Final Roadmap (CODE 2026)

## Core Idea (one-liner for judges)
> "Hamara app stock prices display nahi karta — market data ko interpret karke user ke limited attention ko prioritize karta hai."

---

## 1. FINAL ALGORITHM — Attention Score Engine

**Approach: Explainable Statistical Anomaly Detection (NOT ML/prediction)**

Reasoning to say out loud in judging: *"Humne deliberately ek explainable statistical model choose kiya, black-box predictive model (LSTM/XGBoost) nahi — kyunki product ka goal future price predict karna nahi, balki 'attention worthy' change detect karna hai."*

### Signals (4 components)

**1. Price Return**
```
Return = (Current Price - Previous Price) / Previous Price
```

**2. Abnormality (Z-Score)** ⭐ most important signal
```
mean (μ) and std dev (σ) of last 20 trading days' returns
Z = (Today's Return - μ) / σ
```
- |Z| > 1.5 → moderate anomaly
- |Z| > 2.5 → significant anomaly

**3. Volume Anomaly**
```
Volume Ratio = Today's Volume / 20-day Average Volume
```

**4. Volatility Spike**
```
Volatility Ratio = Current Volatility / Normal (20-day) Volatility
```

### Attention Score (combine + normalize each 0–100 first)
```
Attention Score = 0.35 × PriceScore
                 + 0.30 × ZScore
                 + 0.20 × VolumeScore
                 + 0.15 × VolatilityScore
```
**Judge-defense line for the weights:** "Price movement highest-weighted kyunki it's the most direct user-facing signal; Z-score second kyunki it normalizes for each stock's own baseline; volatility lowest kyunki it's a confirming signal, not primary."

### Score → Human Label
```
0–30    🟢 Normal
30–60   🟡 Moderate
60–80   🟠 Important
80–100  🔴 Significant
```

### ⭐ ADDITION: Sector/Correlation Signal (differentiator)
Agar watchlist ke 2+ stocks same sector, same din, same direction mein unusual move (|Z|>1.5) kar rahe hain → tag as **"Sector-wide move"** instead of individual stock alert.
```
if count(stocks in same sector with |Z| > 1.5 today) >= 2:
    flag_type = "sector_correlation"
else:
    flag_type = "stock_specific"
```
Ye "signal vs noise" ka deeper layer dikhata hai — most teams isko miss karenge.

---

## 2. Snapshot / "Since Last Visit" Logic

```
On visit  → save snapshot (user_id, symbol, price, volume, timestamp)
On return → fetch old snapshot vs current data
          → run Attention Score engine on the diff window
          → rank descending → show top N
update last_viewed_at per USER (not per device) → auto multi-device sync
```

---

## 3. Finalized Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + Tailwind + Recharts | Fast to build, good charts |
| Backend | FastAPI (Python) | Async, easy to write change_engine as separate module |
| DB | PostgreSQL | Relational + time-series snapshots |
| Cache | Redis (TTL = poll interval) | Dedup fan-out, avoid rate limits |
| Market Data | **yfinance** (primary) + Finnhub (backup) | Alpha Vantage free tier = only 5 calls/min, too limited for a demo |
| Background Jobs | APScheduler | Simple, no separate infra needed like Celery |
| Auth | JWT (add LAST, not first) | MVP core first |

---

## 4. PHASE-BY-PHASE PLAN (exact order — do not skip ahead)

### 🔵 Phase 1 — Skeleton (30–45 min)
- Create repo, `backend/` + `frontend/` folders
- FastAPI boilerplate with `/health` endpoint
- React app boilerplate (Vite)
- Postgres connection tested (local or Supabase/Neon free tier)

### 🔵 Phase 2 — Watchlist CRUD (45–60 min)
- No market data yet, just structure
- Endpoints: `POST /watchlists`, `GET /watchlists`, `POST /watchlists/{id}/stocks`, `DELETE /watchlists/{id}/stocks/{symbol}`
- DB constraint: `UNIQUE(watchlist_id, symbol)` — prevents duplicate stock bug

### 🔵 Phase 3 — Market Data Integration (45–60 min)
- Connect yfinance
- `GET /market/{symbol}` → returns price, volume, change%
- Test with 3–4 hardcoded stocks first before scaling

### 🔵 Phase 4 — Historical Baseline (30–45 min)
- Pull last 20–30 trading days per stock
- Compute: mean return (μ), std dev (σ), avg volume, avg volatility
- Cache this in Redis (recompute daily, not every request)

### 🔥 Phase 5 — Meaningful Change Engine (60–90 min) ⭐ CORE MODULE
Build as standalone `change_engine.py`:
```
calculate_return()
calculate_z_score()
calculate_volume_ratio()
calculate_volatility_ratio()
calculate_sector_correlation()   ← added
calculate_attention_score()
classify_attention()
```
This is the module you'll explain in detail to judges — keep it clean and testable in isolation.

### 🔵 Phase 6 — Snapshot System (30–45 min)
- Save snapshot on visit
- `GET /watchlists/{id}/changes` → old vs current → run engine → return ranked list

### 🔵 Phase 7 — Dashboard UI (60–90 min)
- "Welcome back, X changes since last visit" hero section
- Ranked cards with 🔴🟠🟡🟢 + attention score + one-line reason
- Full watchlist table below

### 🔵 Phase 8 — Stock Detail Page (45–60 min)
- Individual candlestick chart (Recharts/Lightweight Charts) — NOT combined
- "Since your last visit" delta block
- "Why it matters" explanation block

### 🔵 Phase 9 — Resilience / Edge Cases (45–60 min) ⭐ HIGH JUDGE VALUE
- API down → show cached data + "Market data unavailable, last updated: X"
- Stale data (>X min old) → "⚠ Data delayed" badge
- Market closed → "Last traded price" label
- New stock (no baseline yet) → "Tracking started today, comparison next visit"
- **Retry + backoff on external API calls** (added — simple `try/except` with 2–3 retries, exponential backoff)
- **Circuit breaker**: if API fails N times in a row, serve stale cache instead of erroring
- Long absence (20+ days) → summarize instead of flooding: "3 significant, 5 moderate changes. Biggest mover: X"

### 🔵 Phase 10 — News Context (OPTIONAL, only if time left, 30–45 min)
- Fetch related headlines for top 2–3 flagged stocks only
- Label as "Related context" — never claim causation

### 🔵 Phase 11 — Polish (remaining time)
- Loading skeletons, empty states, responsive layout, tooltips
- `/health` and basic request logging (shows production-mindedness)

---

## 5. If Time Runs Out — Cut in THIS Order (last cut first)
1. News/context (Phase 10)
2. Sector correlation (nice-to-have differentiator, cut if truly short on time)
3. Full polish/animations
4. Auth (can demo without login, single hardcoded user)
5. **Never cut:** Change Engine (Phase 5), Snapshot diffing (Phase 6), Dashboard (Phase 7) — these ARE the product

---

## 6. Final Pitch Line for Judges
> "Most watchlists show you numbers. Ours tells you what's actually worth your attention — using volatility-normalized statistical significance instead of flat thresholds, diffed against what you last saw, with sector-aware noise filtering — all fully explainable, no black box."


// Falls back to the standard local backend port when VITE_API_URL isn't
// set (e.g. a fresh clone with no .env yet) — without this, a missing
// .env silently sends every request to the Vite dev server itself
// instead of the API, which looks like a broken app rather than a
// missing config file.
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

function debugQuery() {
  if (typeof window === 'undefined') return ''
  const params = new URLSearchParams(window.location.search)
  const out = new URLSearchParams()
  for (const key of ['force_fail', 'force_stale', 'force_market', 'force_disagree']) {
    if (params.has(key)) out.set(key, params.get(key))
  }
  const serialized = out.toString()
  return serialized ? `?${serialized}` : ''
}

function withDebug(path) {
  const extra = debugQuery()
  if (!extra) return path
  return path.includes('?') ? `${path}&${extra.slice(1)}` : `${path}${extra}`
}

async function request(path, options) {
  const response = await fetch(`${API_BASE}${withDebug(path)}`, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    ...options,
  })
  if (!response.ok) {
    const raw = await response.text()
    // FastAPI errors come back as {"detail": "..."} — surface just the
    // message so a duplicate-symbol or validation error reads cleanly in
    // the UI instead of showing raw JSON.
    let message = raw
    try {
      const parsed = JSON.parse(raw)
      if (typeof parsed?.detail === 'string') {
        message = parsed.detail
      } else if (Array.isArray(parsed?.detail)) {
        message = parsed.detail.map((item) => item.msg).filter(Boolean).join('; ')
      }
    } catch {
      // not JSON — fall back to the raw text below
    }
    throw new Error(message || `${response.status} ${response.statusText}`)
  }
  return response.json()
}

export function listWatchlists() {
  return request('/watchlists?user_id=1')
}

export function createWatchlist(payload) {
  return request('/watchlists', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function addStock(watchlistId, { symbol, sector }) {
  return request(`/watchlists/${watchlistId}/stocks`, {
    method: 'POST',
    body: JSON.stringify({ symbol, sector: sector ?? '' }),
  })
}

export function removeStock(watchlistId, symbol) {
  return request(`/watchlists/${watchlistId}/stocks/${encodeURIComponent(symbol)}`, {
    method: 'DELETE',
  })
}

export function updateAlertSettings(watchlistId, { enabled, threshold }) {
  return request(`/watchlists/${watchlistId}/alert-settings`, {
    method: 'PATCH',
    body: JSON.stringify({ enabled, threshold: threshold ?? null }),
  })
}

export function fetchWatchlistChanges(watchlistId, sensitivity) {
  const query = sensitivity ? `?sensitivity=${encodeURIComponent(sensitivity)}` : ''
  return request(`/watchlists/${watchlistId}/changes${query}`)
}

export function fetchDiversification(watchlistId) {
  return request(`/watchlists/${watchlistId}/diversification`)
}

export function fetchStockDetail(watchlistId, symbol) {
  return request(`/watchlists/${watchlistId}/stocks/${encodeURIComponent(symbol)}`)
}

export function fetchOhlcv(symbol, range) {
  return request(
    `/market/${encodeURIComponent(symbol)}/ohlcv?range=${encodeURIComponent(range)}`,
  )
}
export function fetchNews(symbol) {
  return request(`/market/${encodeURIComponent(symbol)}/news`)
}
export function searchSymbols(query, { signal } = {}) {
  const q = query.trim()
  if (!q) return Promise.resolve({ results: [] })
  return request(`/market/search?q=${encodeURIComponent(q)}`, { signal })
}

const DEMO_SYMBOLS = ['AAPL', 'MSFT', 'NVDA', 'JPM']

// Resolves which watchlist to show. Prefers `preferredId` (comes from the
// switcher / URL / localStorage) if it still exists; otherwise falls back to
// the first watchlist. Seeds a demo "Core" watchlist the very first time
// there are none at all, same as before multi-watchlist support existed.
export async function ensureWatchlist(preferredId) {
  let lists = await listWatchlists()
  if (!lists.length) {
    await createWatchlist({
      name: 'Core',
      user_id: 1,
      symbols: DEMO_SYMBOLS,
    })
    lists = await listWatchlists()
  }
  const preferred =
    preferredId != null ? lists.find((item) => String(item.id) === String(preferredId)) : null
  return { watchlist: preferred ?? lists[0], watchlists: lists }
}

export async function loadDashboardData(sensitivity, preferredWatchlistId) {
  const { watchlist, watchlists } = await ensureWatchlist(preferredWatchlistId)
  const payload = await fetchWatchlistChanges(watchlist.id, sensitivity)
  return { watchlist, watchlists, ...payload }
}

export async function loadSymbolDetail(symbol, range, preferredWatchlistId) {
  const { watchlist, watchlists } = await ensureWatchlist(preferredWatchlistId)
  const [detail, ohlcv, news] = await Promise.all([
    fetchStockDetail(watchlist.id, symbol),
    fetchOhlcv(symbol, range),
    fetchNews(symbol).catch(() => ({ results: [] })),
  ])
  return { watchlist, watchlists, ...detail, ohlcv, news }
}

const API_BASE = import.meta.env.VITE_API_URL ?? ''

function debugQuery() {
  if (typeof window === 'undefined') return ''
  const params = new URLSearchParams(window.location.search)
  const out = new URLSearchParams()
  for (const key of ['force_fail', 'force_stale', 'force_market']) {
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
    const detail = await response.text()
    throw new Error(detail || `${response.status} ${response.statusText}`)
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

export function fetchWatchlistChanges(watchlistId) {
  return request(`/watchlists/${watchlistId}/changes`)
}

export function fetchStockDetail(watchlistId, symbol) {
  return request(`/watchlists/${watchlistId}/stocks/${encodeURIComponent(symbol)}`)
}

export function fetchOhlcv(symbol, range) {
  return request(
    `/market/${encodeURIComponent(symbol)}/ohlcv?range=${encodeURIComponent(range)}`,
  )
}

const DEMO_SYMBOLS = ['AAPL', 'MSFT', 'NVDA', 'JPM']

export async function ensureDefaultWatchlist() {
  let lists = await listWatchlists()
  if (!lists.length) {
    await createWatchlist({
      name: 'Core',
      user_id: 1,
      symbols: DEMO_SYMBOLS,
    })
    lists = await listWatchlists()
  }
  return lists[0]
}

export async function loadDashboardData() {
  const watchlist = await ensureDefaultWatchlist()
  const payload = await fetchWatchlistChanges(watchlist.id)
  return { watchlist, ...payload }
}

export async function loadSymbolDetail(symbol, range) {
  const watchlist = await ensureDefaultWatchlist()
  const [detail, ohlcv] = await Promise.all([
    fetchStockDetail(watchlist.id, symbol),
    fetchOhlcv(symbol, range),
  ])
  return { watchlist, ...detail, ohlcv }
}

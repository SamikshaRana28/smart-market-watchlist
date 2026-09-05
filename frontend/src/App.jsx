
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { addStock, createWatchlist, loadDashboardData, removeStock, updateAlertSettings } from './api.js'
import AddStockForm from './components/AddStockForm.jsx'
import AlertSettings from './components/AlertSettings.jsx'
import ChangeCard from './components/ChangeCard.jsx'
import Hero from './components/Hero.jsx'
import WatchlistSwitcher from './components/WatchlistSwitcher.jsx'
import WatchlistTable from './components/WatchlistTable.jsx'
import { digestSentence, isMeaningful, sectorCorrelationBanners, watchlistSummaryLine } from './format.js'

const DIGEST_COLLAPSE_COUNT = 5
// Remembers the last-viewed watchlist across reloads when the URL has no
// `?watchlist=` param of its own (e.g. someone bookmarked "/").
const STORAGE_KEY = 'stocklytic:watchlistId'

const SENSITIVITY_OPTIONS = [
  { value: 'conservative', label: 'Conservative' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'aggressive', label: 'Aggressive' },
]

export default function App() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedId, setSelectedId] = useState(() => {
    const fromUrl = searchParams.get('watchlist')
    if (fromUrl) return fromUrl
    if (typeof window === 'undefined') return null
    return window.localStorage.getItem(STORAGE_KEY)
  })
  const [data, setData] = useState(null)
  const [watchlists, setWatchlists] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sensitivity, setSensitivity] = useState('balanced')
  const [showAllMeaningful, setShowAllMeaningful] = useState(false)
  const [isPolling, setIsPolling] = useState(false)

  const refresh = useCallback(
    async (nextSensitivity, preferredId, { silent = false } = {}) => {
      if (silent) {
        setIsPolling(true)
      } else {
        setLoading(true)
      }
      setError(null)
      try {
        const payload = await loadDashboardData(nextSensitivity ?? sensitivity, preferredId ?? selectedId)
        setData(payload)
        setWatchlists(payload.watchlists ?? [])
        const resolvedId = payload.watchlist?.id != null ? String(payload.watchlist.id) : null
        if (resolvedId && resolvedId !== selectedId) {
          setSelectedId(resolvedId)
        }
      } catch (err) {
        // A silent background poll failing shouldn't blow away a working
        // dashboard with an error screen — just skip this tick and try
        // again next interval. A manual/initial load still surfaces it.
        if (!silent) {
          setError(err instanceof Error ? err.message : 'Failed to load watchlist')
        }
      } finally {
        if (silent) {
          setIsPolling(false)
        } else {
          setLoading(false)
        }
      }
    },
    [sensitivity, selectedId],
  )

  useEffect(() => {
    refresh(sensitivity, selectedId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sensitivity, selectedId])

  // Background auto-refresh: quietly re-pull live prices/scores every 45s
  // so the dashboard feels current without the user hitting Refresh. Paused
  // while the tab is hidden so it doesn't burn API calls in a background
  // tab, and paused if a manual load is already in flight.
  useEffect(() => {
    const tick = () => {
      if (document.visibilityState !== 'visible') return
      if (loading) return
      refresh(sensitivity, selectedId, { silent: true })
    }
    const intervalId = window.setInterval(tick, 45000)
    return () => window.clearInterval(intervalId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sensitivity, selectedId])

  // Keep the URL (`?watchlist=`) and localStorage in sync with whichever
  // watchlist is actually selected, so switching persists across a reload
  // and carries into the symbol-detail page via the existing
  // `window.location.search` links.
  useEffect(() => {
    if (!selectedId) return
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, selectedId)
    }
    if (searchParams.get('watchlist') !== selectedId) {
      const next = new URLSearchParams(searchParams)
      next.set('watchlist', selectedId)
      setSearchParams(next, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId])

  const handleSensitivityChange = (event) => {
    setSensitivity(event.target.value)
  }

  const handleSwitchWatchlist = useCallback((id) => {
    setSelectedId(String(id))
    setShowAllMeaningful(false)
  }, [])

  const handleCreateWatchlist = useCallback(async (name) => {
    const created = await createWatchlist({ name, user_id: 1, symbols: [] })
    setSelectedId(String(created.id))
  }, [])

  const watchlistId = data?.watchlist?.id

  const handleAddStock = useCallback(
    async ({ symbol, sector }) => {
      if (!watchlistId) return
      await addStock(watchlistId, { symbol, sector })
      await refresh(sensitivity, String(watchlistId))
    },
    [watchlistId, refresh, sensitivity],
  )

  const handleRemoveStock = useCallback(
    async (symbol) => {
      if (!watchlistId) return
      await removeStock(watchlistId, symbol)
      await refresh(sensitivity, String(watchlistId))
    },
    [watchlistId, refresh, sensitivity],
  )

  const handleSaveAlertSettings = useCallback(
    async ({ enabled, threshold }) => {
      if (!watchlistId) return
      await updateAlertSettings(watchlistId, { enabled, threshold })
      await refresh(sensitivity, String(watchlistId))
    },
    [watchlistId, refresh, sensitivity],
  )

  const changes = data?.changes ?? []
  const meaningful = useMemo(() => changes.filter(isMeaningful), [changes])
  const sectorBanners = useMemo(() => sectorCorrelationBanners(changes), [changes])
  const summaryLine = useMemo(() => watchlistSummaryLine(changes), [changes])
  const digestLine = useMemo(() => digestSentence(data?.summary), [data?.summary])
  const isDigest = Boolean(data?.summary?.is_digest)

  // Long absence (edge case: user returns after weeks) — don't flood the
  // dashboard with every flagged stock, show a handful and let them expand.
  const visibleMeaningful =
    isDigest && !showAllMeaningful ? meaningful.slice(0, DIGEST_COLLAPSE_COUNT) : meaningful
  const hiddenCount = meaningful.length - visibleMeaningful.length

  useEffect(() => {
    setShowAllMeaningful(false)
    // Deliberately watchlist_id only — viewed_at now changes on every
    // background auto-refresh poll too, and resetting this on each poll
    // would collapse an expanded digest list out from under the user
    // while they're reading it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.watchlist_id])

  const isEmpty = !loading && Boolean(data) && changes.length === 0

  // Real browser push (Notification API, foreground): fire once per fetch —
  // `viewed_at` changes on every /changes call, so gate on it rather than on
  // `changes` identity, which would refire on unrelated re-renders.
  const notifiedViewedAtRef = useRef(null)
  useEffect(() => {
    if (!data?.alerts_enabled) return
    if (!data.viewed_at || data.viewed_at === notifiedViewedAtRef.current) return
    notifiedViewedAtRef.current = data.viewed_at

    const triggered = data.triggered_alerts ?? []
    if (!triggered.length) return
    if (typeof window === 'undefined' || !('Notification' in window)) return
    if (Notification.permission !== 'granted') return

    const rowsBySymbol = new Map(changes.map((row) => [row.symbol, row]))
    triggered.forEach((symbol) => {
      const row = rowsBySymbol.get(symbol)
      const score = row?.attention_score != null ? Math.round(row.attention_score) : null
      new Notification(`${symbol} crossed your alert threshold`, {
        body:
          score != null
            ? `Attention Score ${score} on ${data.watchlist?.name ?? 'your watchlist'}.`
            : `New meaningful move on ${data.watchlist?.name ?? 'your watchlist'}.`,
        tag: `alert-${data.watchlist?.id}-${symbol}`,
      })
    })
  }, [data, changes])

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <WatchlistSwitcher
          watchlists={watchlists}
          selectedId={watchlistId}
          onSelect={handleSwitchWatchlist}
          onCreate={handleCreateWatchlist}
          disabled={loading && !data}
        />
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs font-medium text-zinc-600">
            Sensitivity
            <select
              value={sensitivity}
              onChange={handleSensitivityChange}
              className="rounded-lg border border-zinc-200 bg-white px-2 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-zinc-300"
            >
              {SENSITIVITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => refresh(sensitivity, watchlistId != null ? String(watchlistId) : selectedId)}
            className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100"
          >
            Refresh
          </button>
          <span
            className="flex items-center gap-1 text-[11px] text-zinc-400"
            title="Auto-refreshes every 45 seconds while this tab is open"
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${isPolling ? 'bg-emerald-500' : 'bg-zinc-300'}`}
            />
            {isPolling ? 'Updating…' : 'Live'}
          </span>
          <AlertSettings
            watchlist={data?.watchlist}
            onSave={handleSaveAlertSettings}
            disabled={!watchlistId}
          />
        </div>
      </div>

      <Hero
        loading={loading && !data}
        changeCount={meaningful.length}
        lastViewedAt={data?.last_viewed_at}
        watchlistName={data?.watchlist?.name}
        stale={data?.stale}
        marketStatus={data?.market_status}
        lastUpdated={data?.last_updated}
        summaryLine={summaryLine}
        digestLine={digestLine}
      />

      <AddStockForm onAdd={handleAddStock} disabled={!watchlistId} />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Could not load market changes. {error}
        </div>
      )}

      {sectorBanners.map((message) => (
        <div
          key={message}
          className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950"
          role="status"
        >
          {message}
        </div>
      ))}

      {isEmpty ? (
        <div className="rounded-2xl border border-dashed border-zinc-300 bg-white px-6 py-10 text-center">
          <p className="text-sm font-medium text-zinc-700">Your watchlist is empty</p>
          <p className="mt-1 text-sm text-zinc-500">
            Add a symbol above to start tracking it — we&rsquo;ll show you what&rsquo;s
            meaningfully changed from here on.
          </p>
        </div>
      ) : (
        <>
          <section>
            <div className="mb-3 flex items-baseline justify-between">
              <h2 className="text-sm font-semibold text-zinc-900">Worth your attention</h2>
              <p className="text-xs text-zinc-500">Sorted by Attention Score</p>
            </div>
            {loading && !data ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {[0, 1, 2].map((key) => (
                  <div
                    key={key}
                    className="h-32 animate-pulse rounded-xl border border-zinc-200 bg-white"
                  />
                ))}
              </div>
            ) : meaningful.length === 0 ? (
              <p className="rounded-xl border border-dashed border-zinc-200 bg-white px-4 py-6 text-sm text-zinc-500">
                Nothing unusual versus your last visit. Full list is below.
              </p>
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  {visibleMeaningful.map((row) => (
                    <ChangeCard key={row.symbol} row={row} />
                  ))}
                </div>
                {hiddenCount > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowAllMeaningful(true)}
                    className="mt-3 w-full rounded-lg border border-dashed border-zinc-300 bg-white px-4 py-2 text-xs font-medium text-zinc-600 hover:bg-zinc-50"
                  >
                    Show {hiddenCount} more flagged stock{hiddenCount === 1 ? '' : 's'}
                  </button>
                )}
              </>
            )}
          </section>

          {loading && !data ? (
            <div className="h-48 animate-pulse rounded-2xl border border-zinc-200 bg-white" />
          ) : (
            <WatchlistTable rows={changes} onRemove={handleRemoveStock} />
          )}
        </>
      )}
    </main>
  )
}

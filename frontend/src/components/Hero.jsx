import { changeCountLabel } from '../format.js'
import DataStatusBadge from './DataStatusBadge.jsx'

export default function Hero({
  changeCount,
  lastViewedAt,
  watchlistName,
  loading,
  stale,
  marketStatus,
  lastUpdated,
}) {
  const when = lastViewedAt
    ? new Date(lastViewedAt).toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      })
    : null

  const updated =
    lastUpdated && !Number.isNaN(new Date(lastUpdated).getTime())
      ? new Date(lastUpdated).toLocaleTimeString(undefined, { timeStyle: 'short' })
      : null

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white px-6 py-7 shadow-sm sm:px-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-zinc-500">
          {watchlistName ?? 'Watchlist'}
        </p>
        <DataStatusBadge stale={stale} marketStatus={marketStatus} />
      </div>
      {loading ? (
        <div className="mt-4 space-y-3">
          <div className="h-9 w-4/5 max-w-xl animate-pulse rounded-md bg-zinc-100" />
          <div className="h-4 w-48 animate-pulse rounded-md bg-zinc-100" />
        </div>
      ) : (
        <>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-900 sm:text-3xl">
            Welcome back, {changeCountLabel(changeCount)} since your last visit
          </h1>
          <p className="mt-2 text-sm text-zinc-500">
            {when
              ? `Prior snapshot ${when}. Ranked by Attention Score.`
              : 'First visit — we are storing a baseline for next time.'}
            {marketStatus === 'closed' ? ' US cash session is closed.' : ''}
            {stale && updated ? ` Last updated ${updated}.` : ''}
          </p>
        </>
      )}
    </section>
  )
}

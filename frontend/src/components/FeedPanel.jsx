// Feed / data-quality panel: what the polling loop is actually doing right
// now, plus buttons to deliberately break it (outage / stale / disagreeing
// sources) so the resilience layer's honesty is demoable on purpose instead
// of only showing up if the real provider happens to hiccup during a demo.

const STATUS_META = {
  healthy: { label: 'healthy', dot: 'bg-emerald-500' },
  stale: { label: 'stale data', dot: 'bg-amber-500' },
  outage: { label: 'outage', dot: 'bg-red-500' },
  disagree: { label: 'sources disagree', dot: 'bg-violet-500' },
}

const SIMULATE_OPTIONS = [
  { key: 'healthy', label: 'Healthy' },
  { key: 'outage', label: 'Outage' },
  { key: 'stale', label: 'Stale data' },
  { key: 'disagree', label: 'Sources disagree' },
]

function StatRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="font-medium tabular-nums text-zinc-900">{value}</dd>
    </div>
  )
}

export default function FeedPanel({ feed, simulateStatus, onSimulate, loading }) {
  if (loading && !feed) {
    return <div className="h-56 animate-pulse rounded-2xl border border-zinc-200 bg-white" />
  }
  if (!feed) return null

  const meta = STATUS_META[feed.status] ?? STATUS_META.healthy

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-900">Feed</h2>
        <span className="flex items-center gap-1.5 text-xs font-medium text-zinc-600">
          <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
          {meta.label}
        </span>
      </div>

      <dl className="mt-2 divide-y divide-zinc-100 text-xs">
        <StatRow label="Polling" value={`every ${feed.polling_interval_seconds}s`} />
        <StatRow label="Last cycle" value={`${feed.applied} applied, ${feed.rejected} rejected`} />
        <StatRow label="Cycle time" value={`${feed.cycle_time_ms} ms`} />
        <StatRow label="Headline model" value={feed.headline_model} />
        <StatRow
          label="Stored"
          value={`${feed.stored_signals.toLocaleString()} signals · ${feed.bars_fetched} bars this cycle`}
        />
      </dl>

      <p className="mt-3 border-t border-zinc-100 pt-3 text-xs leading-relaxed text-zinc-500">
        Market feeds break, lag and disagree. Break this one on purpose and watch the list
        stay honest about what it knows.
      </p>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SIMULATE_OPTIONS.map((option) => (
          <button
            key={option.key}
            type="button"
            onClick={() => onSimulate?.(option.key)}
            aria-pressed={simulateStatus === option.key}
            className={`rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-colors ${
              simulateStatus === option.key
                ? 'border-zinc-900 bg-zinc-900 text-white'
                : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}

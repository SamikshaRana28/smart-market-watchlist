const LABEL_ORDER = ['Moderate', 'Important', 'Significant']

function formatPercent(value) {
  if (value == null) return '—'
  return `${(value * 100).toFixed(0)}%`
}

export default function AccuracyPanel({ data, loading, onRefresh }) {
  const summary = data?.summary
  const recent = data?.recent ?? []

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-900">Score accuracy</h2>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="text-[11px] font-medium text-zinc-500 hover:text-zinc-800 disabled:opacity-50"
        >
          {loading ? 'Checking…' : 'Check now'}
        </button>
      </div>

      {!summary || summary.total_flagged === 0 ? (
        <p className="text-sm text-zinc-500">
          No flags recorded yet. Once a stock is flagged Moderate or higher, we track whether it
          actually moved further in the days after — a self-audit, not just an assertion.
        </p>
      ) : summary.total_evaluated === 0 ? (
        <p className="text-sm text-zinc-500">
          {summary.total_flagged} flag{summary.total_flagged === 1 ? '' : 's'} recorded so far —
          none are old enough to grade yet. We check back {summary.window_days} trading days after
          a flag.
        </p>
      ) : (
        <>
          <div className="flex items-baseline gap-2">
            <p className="font-mono text-3xl font-semibold text-zinc-900">
              {formatPercent(summary.hit_rate)}
            </p>
            <p className="text-xs text-zinc-500">
              of graded flags moved {Math.round(summary.threshold * 100)}%+ further within{' '}
              {summary.window_days} trading days
            </p>
          </div>
          <p className="mt-1 text-xs text-zinc-500">
            {summary.total_evaluated} graded · {summary.pending_evaluation} still pending
          </p>

          <dl className="mt-4 space-y-2">
            {LABEL_ORDER.map((label) => {
              const bucket = summary.by_label?.[label]
              if (!bucket || bucket.evaluated === 0) return null
              return (
                <div key={label} className="flex items-center justify-between text-xs">
                  <dt className="text-zinc-600">{label}</dt>
                  <dd className="font-mono font-medium text-zinc-800">
                    {formatPercent(bucket.hit_rate)}{' '}
                    <span className="text-zinc-400">({bucket.evaluated})</span>
                  </dd>
                </div>
              )
            })}
          </dl>

          {recent.length > 0 && (
            <div className="mt-4 border-t border-zinc-100 pt-3">
              <p className="mb-2 text-[11px] uppercase tracking-wide text-zinc-400">
                Recent flags
              </p>
              <ul className="space-y-1.5 text-xs">
                {recent.slice(0, 5).map((item) => (
                  <li
                    key={`${item.symbol}-${item.flagged_at}`}
                    className="flex items-center justify-between"
                  >
                    <span className="text-zinc-600">
                      {item.symbol} · {item.attention_label}
                    </span>
                    <span
                      className={
                        !item.evaluated
                          ? 'text-zinc-400'
                          : item.moved_further
                            ? 'font-medium text-emerald-700'
                            : 'text-zinc-500'
                      }
                    >
                      {!item.evaluated ? 'pending' : formatPercent(item.outcome_return)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  )
}
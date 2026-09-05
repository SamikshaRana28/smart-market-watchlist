import { Fragment } from 'react'

// Portfolio-shape panel: how many *independent* bets the watchlist actually
// represents, a correlation heatmap, the most redundant pair, the least
// redundant holding, the largest sector, and a couple of not-yet-held names
// that would diversify the book the most if added.

// Maps a -1..1 correlation to a background color. Near 0 stays close to
// white (independent); the rest slides toward indigo as correlation → 1.
// Negative correlation (rare for equities, but possible) tints teal instead
// so "moves opposite" reads differently from "barely related".
function cellColor(value) {
  if (value == null) return '#f4f4f5' // zinc-100 — undefined pair
  const clamped = Math.max(-1, Math.min(1, value))
  if (clamped >= 0) {
    const t = clamped // 0..1
    const from = [244, 244, 245] // zinc-100
    const to = [67, 56, 202] // indigo-700
    const mix = from.map((c, i) => Math.round(c + (to[i] - c) * t))
    return `rgb(${mix.join(',')})`
  }
  const t = -clamped
  const from = [244, 244, 245]
  const to = [15, 118, 110] // teal-700
  const mix = from.map((c, i) => Math.round(c + (to[i] - c) * t))
  return `rgb(${mix.join(',')})`
}

function concentrationLabel(ratio) {
  if (ratio == null) return null
  if (ratio < 0.45) return 'Concentrated'
  if (ratio < 0.75) return 'Somewhat diversified'
  return 'Well diversified'
}

function CorrelationHeatmap({ symbols, values }) {
  if (!symbols?.length) return null
  const cellSize = symbols.length > 10 ? 14 : 18

  return (
    <div className="mt-3 overflow-x-auto">
      <div className="inline-grid" style={{ gridTemplateColumns: `auto repeat(${symbols.length}, ${cellSize}px)` }}>
        <div />
        {symbols.map((sym) => (
          <div
            key={`col-${sym}`}
            className="flex items-end justify-center pb-1 text-[8px] font-medium text-zinc-400"
            style={{ height: 40, writingMode: 'vertical-rl' }}
            title={sym}
          >
            {sym}
          </div>
        ))}
        {symbols.map((rowSym, rowIdx) => (
          <Fragment key={`row-${rowSym}`}>
            <div className="flex items-center justify-end pr-1.5 text-[9px] font-medium text-zinc-400">
              {rowSym}
            </div>
            {symbols.map((colSym, colIdx) => {
              const value = values?.[rowIdx]?.[colIdx]
              return (
                <div
                  key={`${rowSym}-${colSym}`}
                  title={`${rowSym} · ${colSym}: ${value == null ? 'n/a' : value.toFixed(2)}`}
                  style={{
                    width: cellSize,
                    height: cellSize,
                    backgroundColor: rowIdx === colIdx ? '#18181b' : cellColor(value),
                  }}
                />
              )
            })}
          </Fragment>
        ))}
      </div>
      <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-zinc-400">
        <span>independent</span>
        <span className="h-2 w-16 rounded-full" style={{ background: 'linear-gradient(to right, #f4f4f5, #4338ca)' }} />
        <span>lockstep</span>
      </div>
    </div>
  )
}

export default function DiversificationPanel({ data, loading, onAddSuggestion, addingSymbol }) {
  if (loading && !data) {
    return <div className="h-64 animate-pulse rounded-2xl border border-zinc-200 bg-white" />
  }
  if (!data) return null

  const {
    n,
    independent_bets: independentBets,
    avg_pair_correlation: avgCorr,
    closest_pair: closestPair,
    adds_least: addsLeast,
    largest_sector: largestSector,
    matrix,
    suggestions,
    insufficient_data: insufficientData,
  } = data

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-zinc-900">Diversification</h2>

      {insufficientData ? (
        <p className="mt-2 text-xs text-zinc-500">
          Add at least 2 symbols to see how independent your bets really are.
        </p>
      ) : (
        <>
          <div className="mt-2">
            <span className="text-3xl font-semibold tabular-nums text-zinc-900">
              {independentBets?.toFixed(1)}
            </span>
            <span className="ml-1.5 text-xs text-zinc-500">
              independent bets
              <br />
              across {n} names
            </span>
          </div>

          <p className="mt-2 text-xs leading-relaxed text-zinc-600">
            {concentrationLabel(n ? independentBets / n : null)}. These {n} names move as
            roughly {independentBets?.toFixed(1)} positions
            {largestSector ? `; ${largestSector.sector} alone is ${Math.round(largestSector.pct)}% of the list.` : '.'}
          </p>

          <CorrelationHeatmap symbols={matrix?.symbols} values={matrix?.values} />

          <dl className="mt-3 divide-y divide-zinc-100 border-t border-zinc-100 text-xs">
            <div className="flex items-center justify-between py-1.5">
              <dt className="text-zinc-500">Average pair correlation</dt>
              <dd className="font-medium text-zinc-900">{avgCorr != null ? avgCorr.toFixed(2) : '—'}</dd>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <dt className="text-zinc-500">Closest pair</dt>
              <dd className="font-medium text-zinc-900">
                {closestPair ? `${closestPair.a} · ${closestPair.b} (${closestPair.correlation.toFixed(2)})` : '—'}
              </dd>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <dt className="text-zinc-500">Adds the least</dt>
              <dd className="font-medium text-zinc-900">{addsLeast ? addsLeast.symbol : '—'}</dd>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <dt className="text-zinc-500">Largest sector</dt>
              <dd className="font-medium text-zinc-900">
                {largestSector ? `${largestSector.sector} ${Math.round(largestSector.pct)}%` : '—'}
              </dd>
            </div>
          </dl>

          {suggestions?.length > 0 && (
            <div className="mt-3 border-t border-zinc-100 pt-3">
              <p className="text-xs text-zinc-500">
                Least correlated to what you already hold — click to add:
              </p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {suggestions.map((row) => (
                  <button
                    key={row.symbol}
                    type="button"
                    onClick={() => onAddSuggestion?.(row.symbol)}
                    disabled={addingSymbol === row.symbol}
                    className="rounded-lg border border-zinc-200 bg-zinc-50 px-2 py-1 text-[11px] font-medium text-zinc-700 hover:border-zinc-300 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {row.symbol} {row.avg_correlation.toFixed(2)}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

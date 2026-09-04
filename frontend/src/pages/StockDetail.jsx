import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { loadSymbolDetail } from '../api.js'
import PriceChart from '../components/PriceChart.jsx'
import DataStatusBadge from '../components/DataStatusBadge.jsx'
import {
  formatPercent,
  formatPrice,
  formatScore,
  formatWhen,
  styleFor,
  whyItMatters,
} from '../format.js'

const RANGES = ['1D', '1W', '1M', '3M', '1Y']

export default function StockDetail() {
  const { symbol: rawSymbol } = useParams()
  const symbol = (rawSymbol ?? '').toUpperCase()
  const [range, setRange] = useState('1M')
  const [chartType, setChartType] = useState('candle')
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function run() {
      setLoading(true)
      setError(null)
      try {
        const data = await loadSymbolDetail(symbol, range)
        if (!cancelled) setPayload(data)
      } catch (err) {
        if (!cancelled) {
          setPayload(null)
          setError(err instanceof Error ? err.message : 'Failed to load symbol')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    if (symbol) run()
    return () => {
      cancelled = true
    }
  }, [symbol, range])

  useEffect(() => {
    setChartType(range === '1D' ? 'line' : 'candle')
  }, [range])

  const change = payload?.change
  const tone = styleFor(change?.attention_label)
  const up = (change?.price_return ?? 0) >= 0
  const explanations = useMemo(() => whyItMatters(change), [change])
  const bars = payload?.ohlcv?.bars ?? []
  const stale = Boolean(change?.stale || payload?.stale || payload?.ohlcv?.stale)
  const marketStatus =
    change?.market_status || payload?.market_status || payload?.ohlcv?.market_status

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <div>
        <Link to={`/${typeof window !== 'undefined' ? window.location.search : ''}`} className="text-xs font-medium text-zinc-500 hover:text-zinc-800">
          ← Back to watchlist
        </Link>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">{symbol}</h1>
              {change?.attention_label && (
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tone.badge}`}>
                  {tone.label}
                </span>
              )}
              <DataStatusBadge stale={stale} marketStatus={marketStatus} />
            </div>
            <p className="mt-1 font-mono text-xl text-zinc-800">
              {formatPrice(change?.current_price)}
            </p>
            <p className="mt-0.5 text-xs text-zinc-500">
              {stale
                ? 'Delayed quote — last known price'
                : marketStatus === 'closed'
                  ? 'Last traded price'
                  : 'Last price'}
            </p>
          </div>
          {change?.attention_score != null && (
            <div className="text-right">
              <p className="text-[11px] uppercase tracking-wide text-zinc-500">Attention</p>
              <p className={`font-mono text-2xl font-semibold ${tone.score}`}>
                {formatScore(change.attention_score)}
              </p>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Could not load this symbol. {error}
        </div>
      )}

      <section className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5">
            {RANGES.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setRange(item)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                  range === item
                    ? 'bg-white text-zinc-900 shadow-sm'
                    : 'text-zinc-500 hover:text-zinc-800'
                }`}
              >
                {item}
              </button>
            ))}
          </div>
          <div className="flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5">
            {['candle', 'line'].map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setChartType(item)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium capitalize ${
                  chartType === item
                    ? 'bg-white text-zinc-900 shadow-sm'
                    : 'text-zinc-500 hover:text-zinc-800'
                }`}
              >
                {item === 'candle' ? 'Candles' : 'Line'}
              </button>
            ))}
          </div>
        </div>
        {loading && !bars.length ? (
          <div className="h-80 animate-pulse rounded-xl bg-zinc-100" />
        ) : (
          <PriceChart bars={bars} range={range} chartType={chartType} />
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-zinc-900">Since your last visit</h2>
          {loading && !change ? (
            <div className="mt-4 h-24 animate-pulse rounded-lg bg-zinc-100" />
          ) : change?.status === 'tracking_started_today' ? (
            <p className="mt-3 text-sm text-zinc-600">
              First snapshot for {symbol} is stored. Price change versus last visit will show
              after you come back.
            </p>
          ) : (
            <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-500">Prior price</dt>
                <dd className="mt-1 font-mono text-zinc-900">{formatPrice(change?.previous_price)}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-500">Now</dt>
                <dd className="mt-1 font-mono text-zinc-900">{formatPrice(change?.current_price)}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-500">Delta</dt>
                <dd
                  className={`mt-1 font-mono font-medium ${
                    change?.price_return == null
                      ? 'text-zinc-400'
                      : up
                        ? 'text-emerald-700'
                        : 'text-red-700'
                  }`}
                >
                  {formatPercent(change?.price_return)}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-500">Prior snapshot</dt>
                <dd className="mt-1 text-zinc-700">{formatWhen(change?.snapshot_at) ?? '—'}</dd>
              </div>
            </dl>
          )}
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-zinc-900">Why it matters</h2>
          {loading && !change ? (
            <div className="mt-4 h-24 animate-pulse rounded-lg bg-zinc-100" />
          ) : (
            <ul className="mt-3 space-y-2.5 text-sm leading-relaxed text-zinc-600">
              {explanations.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  )
}

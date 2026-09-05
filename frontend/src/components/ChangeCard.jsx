import { Link } from 'react-router-dom'
import { formatPercent, formatPrice, formatScore, oneLineReason, reasonIcon, styleFor } from '../format.js'
import DataStatusBadge from './DataStatusBadge.jsx'

export default function ChangeCard({ row }) {
  const tone = styleFor(row.attention_label)
  const up = (row.price_return ?? 0) >= 0

  return (
    <Link
      to={`/symbol/${row.symbol}${typeof window !== 'undefined' ? window.location.search : ''}`}
      className={`relative block overflow-hidden rounded-xl border p-4 ${tone.card}`}
    >
      <span className={`absolute inset-y-0 left-0 w-1 ${tone.bar}`} aria-hidden />
      <div className="flex items-start justify-between gap-3 pl-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold tracking-tight text-zinc-900">
              {row.symbol}
            </h3>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tone.badge}`}
            >
              {tone.label}
            </span>
            <DataStatusBadge
              stale={row.stale}
              marketStatus={row.market_status}
              size="xs"
            />
          </div>
          <p className="mt-2 flex items-start gap-1.5 text-sm leading-snug text-zinc-600">
            {reasonIcon(row) && (
              <span aria-hidden className="leading-snug">
                {reasonIcon(row)}
              </span>
            )}
            <span>{oneLineReason(row)}</span>
          </p>
        </div>
        <div className="text-right">
          <p className="font-mono text-sm font-medium text-zinc-900">
            {formatPrice(row.current_price, row.currency)}
          </p>
          <p
            className={`font-mono text-sm font-medium ${
              up ? 'text-emerald-700' : 'text-red-700'
            }`}
          >
            {formatPercent(row.price_return)}
          </p>
        </div>
      </div>
      <div className="mt-3 flex items-baseline justify-between border-t border-black/5 pt-3 pl-2">
        <span className="text-[11px] uppercase tracking-wide text-zinc-500">
          Attention
        </span>
        <span className={`font-mono text-xl font-semibold tabular-nums ${tone.score}`}>
          {formatScore(row.attention_score)}
        </span>
      </div>
    </Link>
  )
}

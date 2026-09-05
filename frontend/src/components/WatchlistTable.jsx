import { Link } from 'react-router-dom'
import {
  formatPercent,
  formatPrice,
  formatScore,
  formatVolume,
  oneLineReason,
  reasonIcon,
  styleFor,
} from '../format.js'
import DataStatusBadge from './DataStatusBadge.jsx'

function statusLabel(row) {
  if (row.status === 'tracking_started_today') return 'New'
  if (row.status === 'market_data_unavailable') return 'Delayed'
  return styleFor(row.attention_label).label
}

export default function WatchlistTable({ rows, onRemove }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
      <div className="flex items-baseline justify-between border-b border-zinc-100 px-5 py-4">
        <h2 className="text-sm font-semibold text-zinc-900">Full watchlist</h2>
        <p className="text-xs text-zinc-500">{rows.length} names</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-zinc-50 text-[11px] uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-5 py-2.5 font-medium">Symbol</th>
              <th className="px-3 py-2.5 font-medium">Price</th>
              <th className="px-3 py-2.5 font-medium">Change</th>
              <th className="px-3 py-2.5 font-medium">Volume</th>
              <th className="px-3 py-2.5 font-medium">Score</th>
              <th className="px-3 py-2.5 font-medium">Flag</th>
              <th className="px-5 py-2.5 font-medium">Why</th>
              {onRemove && <th className="px-3 py-2.5 font-medium" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {rows.map((row) => {
              const tone = styleFor(row.attention_label)
              const up = (row.price_return ?? 0) >= 0
              return (
                <tr key={row.symbol} className="hover:bg-zinc-50/80">
                  <td className="px-5 py-3 font-semibold text-zinc-900">
                    <Link
                      to={`/symbol/${row.symbol}${typeof window !== 'undefined' ? window.location.search : ''}`}
                      className="hover:underline"
                    >
                      {row.symbol}
                    </Link>
                  </td>
                  <td className="px-3 py-3 font-mono tabular-nums text-zinc-800">
                    <div>{formatPrice(row.current_price, row.currency)}</div>
                    <div className="mt-1">
                      <DataStatusBadge
                        stale={row.stale}
                        marketStatus={row.market_status}
                        size="xs"
                      />
                    </div>
                  </td>
                  <td
                    className={`px-3 py-3 font-mono tabular-nums ${
                      row.price_return == null
                        ? 'text-zinc-400'
                        : up
                          ? 'text-emerald-700'
                          : 'text-red-700'
                    }`}
                  >
                    {formatPercent(row.price_return)}
                  </td>
                  <td className="px-3 py-3 font-mono tabular-nums text-zinc-600">
                    {formatVolume(row.current_volume)}
                  </td>
                  <td className={`px-3 py-3 font-mono tabular-nums font-medium ${tone.score}`}>
                    {formatScore(row.attention_score)}
                  </td>
                  <td className="px-3 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tone.badge}`}>
                      {statusLabel(row)}
                    </span>
                  </td>
                  <td className="max-w-xs truncate px-5 py-3 text-zinc-600">
                    {reasonIcon(row) && <span aria-hidden>{reasonIcon(row)} </span>}
                    {oneLineReason(row)}
                  </td>
                  {onRemove && (
                    <td className="px-3 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => onRemove(row.symbol)}
                        aria-label={`Remove ${row.symbol} from watchlist`}
                        className="rounded-md px-2 py-1 text-xs font-medium text-zinc-400 hover:bg-red-50 hover:text-red-600"
                      >
                        Remove
                      </button>
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

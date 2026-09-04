import { useState } from 'react'

const SECTOR_OPTIONS = [
  '',
  'Technology',
  'Financials',
  'Healthcare',
  'Energy',
  'Consumer',
  'Industrials',
  'Automotive',
  'Communication Services',
]

export default function AddStockForm({ onAdd, disabled }) {
  const [symbol, setSymbol] = useState('')
  const [sector, setSector] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (event) => {
    event.preventDefault()
    const ticker = symbol.trim().toUpperCase()
    if (!ticker) return

    setSubmitting(true)
    setError(null)
    try {
      await onAdd({ symbol: ticker, sector })
      setSymbol('')
      setSector('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add symbol')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-center gap-2 rounded-xl border border-zinc-200 bg-white p-3"
    >
      <input
        type="text"
        value={symbol}
        onChange={(event) => setSymbol(event.target.value)}
        placeholder="Add symbol (e.g. TSLA)"
        maxLength={16}
        disabled={disabled || submitting}
        className="min-w-[10rem] flex-1 rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-300"
      />
      <select
        value={sector}
        onChange={(event) => setSector(event.target.value)}
        disabled={disabled || submitting}
        className="rounded-lg border border-zinc-200 bg-white px-2 py-1.5 text-sm text-zinc-700 focus:outline-none focus:ring-2 focus:ring-zinc-300"
      >
        <option value="">Sector (optional)</option>
        {SECTOR_OPTIONS.filter(Boolean).map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <button
        type="submit"
        disabled={disabled || submitting || !symbol.trim()}
        className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? 'Adding…' : '+ Add'}
      </button>
      {error && <p className="w-full text-xs text-red-600">{error}</p>}
    </form>
  )
}

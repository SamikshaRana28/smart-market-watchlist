import { useState } from 'react'

export default function WatchlistSwitcher({ watchlists, selectedId, onSelect, onCreate, disabled }) {
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const handleCreate = async (event) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    setSubmitting(true)
    setError(null)
    try {
      await onCreate(trimmed)
      setName('')
      setCreating(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create watchlist')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Watchlists">
        {watchlists.map((list) => {
          const active = String(list.id) === String(selectedId)
          return (
            <button
              key={list.id}
              type="button"
              role="tab"
              aria-selected={active}
              disabled={disabled}
              onClick={() => onSelect(list.id)}
              title={list.name}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                active
                  ? 'bg-zinc-900 text-white'
                  : 'border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-100'
              } disabled:cursor-not-allowed disabled:opacity-50`}
            >
              {list.name}
              {Array.isArray(list.symbols) && (
                <span className={active ? 'ml-1.5 text-zinc-300' : 'ml-1.5 text-zinc-400'}>
                  {list.symbols.length}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {creating ? (
        <form onSubmit={handleCreate} className="flex items-center gap-1.5">
          <input
            autoFocus
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Watchlist name"
            maxLength={120}
            disabled={submitting}
            className="w-36 rounded-lg border border-zinc-200 px-2 py-1.5 text-xs text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
          <button
            type="submit"
            disabled={submitting || !name.trim()}
            className="rounded-lg bg-zinc-900 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? '…' : 'Create'}
          </button>
          <button
            type="button"
            onClick={() => {
              setCreating(false)
              setName('')
              setError(null)
            }}
            className="rounded-lg px-2 py-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-800"
          >
            Cancel
          </button>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setCreating(true)}
          disabled={disabled}
          className="rounded-lg border border-dashed border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-500 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          + New watchlist
        </button>
      )}
      {error && <p className="w-full basis-full text-xs text-red-600">{error}</p>}
    </div>
  )
}

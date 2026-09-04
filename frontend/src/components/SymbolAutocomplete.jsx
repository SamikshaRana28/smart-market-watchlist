import { useEffect, useRef, useState } from 'react'
import { searchSymbols } from '../api.js'

const DEBOUNCE_MS = 200

/**
 * Ticker/company-name search box. Lets someone type "google" and pick GOOGL
 * from a dropdown instead of having to already know the exact ticker.
 *
 * Fully controlled on the *text* value (`value` / `onChange`) so the parent
 * form still owns what gets submitted; this component only adds the
 * suggestion dropdown and an `onSelect(result)` callback for when a specific
 * suggestion is chosen (which carries the resolved symbol + company name).
 */
export default function SymbolAutocomplete({
  value,
  onChange,
  onSelect,
  disabled,
  placeholder,
  inputClassName,
}) {
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [highlighted, setHighlighted] = useState(-1)
  const containerRef = useRef(null)
  const debounceRef = useRef(null)
  const abortRef = useRef(null)
  const skipNextFetchRef = useRef(false)

  useEffect(() => {
    return () => {
      clearTimeout(debounceRef.current)
      abortRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    // Selecting a suggestion updates `value` too; don't immediately re-query
    // for the exact string we just picked.
    if (skipNextFetchRef.current) {
      skipNextFetchRef.current = false
      return
    }

    clearTimeout(debounceRef.current)
    const query = value.trim()
    if (query.length < 1) {
      setResults([])
      setOpen(false)
      setLoading(false)
      return
    }

    debounceRef.current = setTimeout(async () => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setLoading(true)
      try {
        const data = await searchSymbols(query, { signal: controller.signal })
        setResults(data.results ?? [])
        setOpen(true)
        setHighlighted(-1)
      } catch (err) {
        if (err?.name !== 'AbortError') setResults([])
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }, DEBOUNCE_MS)

    return () => clearTimeout(debounceRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const commitSelection = (result) => {
    skipNextFetchRef.current = true
    setOpen(false)
    setResults([])
    setHighlighted(-1)
    onChange(result.symbol)
    onSelect?.(result)
  }

  const handleKeyDown = (event) => {
    if (!open || results.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlighted((prev) => (prev + 1) % results.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlighted((prev) => (prev <= 0 ? results.length - 1 : prev - 1))
    } else if (event.key === 'Enter') {
      if (highlighted >= 0 && highlighted < results.length) {
        event.preventDefault()
        commitSelection(results[highlighted])
      }
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div ref={containerRef} className="relative min-w-[10rem] flex-1">
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        maxLength={16}
        disabled={disabled}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        autoComplete="off"
        className={inputClassName}
      />
      {open && (results.length > 0 || loading) && (
        <ul className="absolute left-0 right-0 top-full z-20 mt-1 max-h-64 overflow-y-auto rounded-lg border border-zinc-200 bg-white py-1 shadow-lg">
          {loading && results.length === 0 && (
            <li className="px-3 py-2 text-xs text-zinc-400">Searching…</li>
          )}
          {results.map((result, index) => (
            <li key={result.symbol}>
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => commitSelection(result)}
                onMouseEnter={() => setHighlighted(index)}
                className={`flex w-full items-center justify-between gap-3 px-3 py-1.5 text-left text-sm ${
                  index === highlighted ? 'bg-zinc-100' : 'hover:bg-zinc-50'
                }`}
              >
                <span className="flex flex-col">
                  <span className="font-medium text-zinc-900">{result.symbol}</span>
                  <span className="truncate text-xs text-zinc-500">{result.name}</span>
                </span>
                {result.exchange && (
                  <span className="shrink-0 text-xs text-zinc-400">{result.exchange}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

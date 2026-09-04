import { useEffect, useState } from 'react'

const DEFAULT_THRESHOLD = 75

// Real browser push (Notification API): permission lives on the browser, not
// our server, so we always read it fresh rather than trusting stale state.
function currentPermission() {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'unsupported'
  return Notification.permission
}

export default function AlertSettings({ watchlist, onSave, disabled }) {
  const [open, setOpen] = useState(false)
  const [enabled, setEnabled] = useState(false)
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD)
  const [permission, setPermission] = useState(currentPermission)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  // Re-sync local state whenever the server copy changes — switching
  // watchlists, or a save round-trip coming back through `data.watchlist`.
  useEffect(() => {
    setEnabled(Boolean(watchlist?.alerts_enabled))
    setThreshold(watchlist?.alert_threshold ?? DEFAULT_THRESHOLD)
    setError(null)
  }, [watchlist?.id, watchlist?.alerts_enabled, watchlist?.alert_threshold])

  const persist = async (nextEnabled, nextThreshold) => {
    setSaving(true)
    setError(null)
    try {
      await onSave({ enabled: nextEnabled, threshold: nextThreshold })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save alert settings')
      // Server rejected it — snap the toggle back to what's actually saved.
      setEnabled(Boolean(watchlist?.alerts_enabled))
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async () => {
    if (enabled) {
      setEnabled(false)
      await persist(false, threshold)
      return
    }

    if (permission === 'unsupported') {
      setError('This browser does not support notifications.')
      return
    }

    let result = permission
    if (result !== 'granted') {
      result = await Notification.requestPermission()
      setPermission(result)
    }
    if (result !== 'granted') {
      setError('Notifications are blocked — allow them for this site to get alerts.')
      return
    }

    setEnabled(true)
    await persist(true, threshold)
  }

  const handleThresholdCommit = async () => {
    const clamped = Math.min(100, Math.max(0, Math.round(Number(threshold) || 0)))
    setThreshold(clamped)
    if (enabled) {
      await persist(true, clamped)
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        disabled={disabled}
        aria-expanded={open}
        className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
          enabled
            ? 'border-zinc-900 bg-zinc-900 text-white'
            : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50'
        } disabled:cursor-not-allowed disabled:opacity-50`}
      >
        Alerts{enabled ? ` \u2265 ${threshold}` : ''}
      </button>

      {open && (
        <div className="absolute right-0 z-10 mt-2 w-64 rounded-xl border border-zinc-200 bg-white p-3 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-900">Browser notifications</span>
            <button
              type="button"
              role="switch"
              aria-checked={enabled}
              onClick={handleToggle}
              disabled={saving}
              className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${
                enabled ? 'bg-zinc-900' : 'bg-zinc-200'
              } disabled:cursor-not-allowed disabled:opacity-50`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                  enabled ? 'translate-x-4' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>

          <p className="mt-2 text-xs text-zinc-500">
            Notify me when any symbol&rsquo;s Attention Score reaches:
          </p>
          <div className="mt-1.5 flex items-center gap-2">
            <input
              type="number"
              min={0}
              max={100}
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
              onBlur={handleThresholdCommit}
              disabled={saving}
              className="w-16 rounded-lg border border-zinc-200 px-2 py-1 text-xs text-zinc-900 focus:outline-none focus:ring-2 focus:ring-zinc-300 disabled:opacity-50"
            />
            <span className="text-xs text-zinc-500">/ 100</span>
            {saving && <span className="text-xs text-zinc-400">Saving&hellip;</span>}
          </div>

          {permission === 'denied' && (
            <p className="mt-2 text-xs text-amber-700">
              Notifications are blocked in your browser settings for this site.
            </p>
          )}
          {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
        </div>
      )}
    </div>
  )
}

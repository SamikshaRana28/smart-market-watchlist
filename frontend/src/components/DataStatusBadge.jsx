export default function DataStatusBadge({ stale, marketStatus, size = 'sm' }) {
  const cls =
    size === 'xs'
      ? 'rounded px-1.5 py-0.5 text-[10px] font-medium'
      : 'rounded-full px-2 py-0.5 text-[11px] font-medium'

  if (stale) {
    return (
      <span className={`${cls} bg-amber-100 text-amber-900`} title="Quote is older than 5 minutes or served from cache">
        Data delayed
      </span>
    )
  }
  if (marketStatus === 'closed') {
    return (
      <span className={`${cls} bg-zinc-100 text-zinc-600`} title="US cash session is closed">
        Last traded
      </span>
    )
  }
  return null
}

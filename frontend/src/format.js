export const MEANINGFUL_LABELS = new Set(['moderate', 'important', 'significant'])

export const CLASSIFICATION = {
  significant: {
    label: 'Significant',
    card: 'border-red-200 bg-red-50/80',
    bar: 'bg-red-500',
    badge: 'bg-red-100 text-red-800',
    score: 'text-red-700',
  },
  important: {
    label: 'Important',
    card: 'border-orange-200 bg-orange-50/80',
    bar: 'bg-orange-500',
    badge: 'bg-orange-100 text-orange-800',
    score: 'text-orange-700',
  },
  moderate: {
    label: 'Moderate',
    card: 'border-amber-200 bg-amber-50/80',
    bar: 'bg-amber-400',
    badge: 'bg-amber-100 text-amber-900',
    score: 'text-amber-800',
  },
  normal: {
    label: 'Normal',
    card: 'border-emerald-200 bg-emerald-50/70',
    bar: 'bg-emerald-500',
    badge: 'bg-emerald-100 text-emerald-800',
    score: 'text-emerald-700',
  },
}

export function styleFor(label) {
  return CLASSIFICATION[label] ?? CLASSIFICATION.normal
}

export function isMeaningful(row) {
  return row.status === 'compared' && MEANINGFUL_LABELS.has(row.attention_label)
}

export function formatPrice(value) {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

export function formatPercent(returnFraction) {
  if (returnFraction == null || Number.isNaN(returnFraction)) return '—'
  const pct = returnFraction * 100
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

export function formatVolume(value) {
  if (value == null) return '—'
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

export function formatScore(score) {
  if (score == null) return '—'
  return Number(score).toFixed(1)
}

export function oneLineReason(row) {
  if (row.status === 'tracking_started_today') {
    return 'Tracking started today — comparison next visit'
  }
  if (row.status === 'market_data_unavailable') {
    return 'Market data unavailable'
  }
  if (row.flag_type === 'sector_correlation') {
    return 'Sector-wide move — peers unusual the same day'
  }

  const breakdown = row.breakdown ?? {}
  const candidates = [
    {
      score: breakdown.volume_score ?? 0,
      text:
        row.volume_ratio != null
          ? `Volume ${Number(row.volume_ratio).toFixed(1)}x normal`
          : null,
    },
    {
      score: breakdown.z_score_normalized ?? 0,
      text:
        row.z_score != null
          ? `${Math.abs(row.z_score).toFixed(1)}σ vs 20-day baseline`
          : null,
    },
    {
      score: breakdown.price_score ?? 0,
      text:
        row.price_return != null
          ? `Price ${formatPercent(row.price_return)} since last visit`
          : null,
    },
    {
      score: breakdown.volatility_score ?? 0,
      text:
        row.volatility_ratio != null
          ? `Volatility ${Number(row.volatility_ratio).toFixed(1)}x normal`
          : null,
    },
  ].filter((item) => item.text)

  candidates.sort((a, b) => b.score - a.score)
  return candidates[0]?.text ?? 'Move is within the recent baseline'
}

export function changeCountLabel(count) {
  return count === 1 ? '1 change' : `${count} changes`
}

const SECTOR_SHORT_NAME = {
  technology: 'tech',
  'information technology': 'tech',
}

export function sectorCorrelationBanners(rows) {
  const bySector = new Map()
  for (const row of rows) {
    if (row.flag_type !== 'sector_correlation' || !row.sector) continue
    const members = bySector.get(row.sector) ?? []
    members.push(row)
    bySector.set(row.sector, members)
  }

  return [...bySector.entries()]
    .filter(([, members]) => members.length >= 2)
    .sort((a, b) => b[1].length - a[1].length)
    .map(([sector, members]) => {
      const key = String(sector).trim().toLowerCase()
      const label = SECTOR_SHORT_NAME[key] ?? key
      return `${members.length} ${label} stocks moved together today — likely sector-wide, not stock-specific.`
    })
}

export function formatWhen(iso) {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function zScoreSentence(zScore) {
  const abs = Math.abs(zScore)
  const sigma = `${abs.toFixed(1)}σ`
  if (abs < 1) {
    return `Today's return sits ${sigma} from this stock's 20-day average — close to typical for this name.`
  }
  if (abs < 2) {
    return `The move is ${sigma} versus the 20-day baseline — noticeable, but not extreme.`
  }
  return `The move is ${sigma} versus the 20-day baseline — statistically unusual for this stock.`
}

function volumeSentence(volumeRatio) {
  const x = Number(volumeRatio).toFixed(1)
  if (volumeRatio >= 1.5) {
    return `Volume is ${x}× the 20-day average, so more traders than usual are participating.`
  }
  if (volumeRatio >= 1) {
    return `Volume is about ${x}× the 20-day average — in line with a normal session.`
  }
  return `Volume is ${x}× the 20-day average, so this move does not have heavy participation.`
}

function volatilitySentence(volatilityRatio) {
  const x = Number(volatilityRatio).toFixed(1)
  if (volatilityRatio >= 1.5) {
    return `The high–low range is ${x}× typical, so the session is choppier than this stock's recent average.`
  }
  if (volatilityRatio >= 1) {
    return `Intraday range is about ${x}× the 20-day average — not an unusually wide day.`
  }
  return `The session range is ${x}× typical, quieter than this stock's recent average.`
}

export function whyItMatters(row) {
  if (!row) return []
  if (row.status === 'tracking_started_today') {
    return [
      'Tracking started today. We stored a snapshot instead of inventing a move from an empty baseline — the Attention Score appears after your next visit.',
    ]
  }
  if (row.status === 'market_data_unavailable') {
    return ['Live market data is unavailable for this symbol, so there is no Attention Score to explain.']
  }

  const lines = []
  if (row.flag_type === 'sector_correlation') {
    lines.push(
      'Peers in the same sector also look unusual today, so this may be a sector move rather than a stock-specific story.',
    )
  }
  if (row.z_score != null) lines.push(zScoreSentence(row.z_score))
  if (row.volume_ratio != null) lines.push(volumeSentence(row.volume_ratio))
  if (row.volatility_ratio != null) lines.push(volatilitySentence(row.volatility_ratio))

  const breakdown = row.breakdown
  if (breakdown && row.attention_score != null) {
    const weights = [
      { name: 'price vs last visit', score: breakdown.price_score },
      { name: 'statistical surprise (z-score)', score: breakdown.z_score_normalized },
      { name: 'volume', score: breakdown.volume_score },
      { name: 'volatility', score: breakdown.volatility_score },
    ].sort((a, b) => b.score - a.score)
    const top = weights[0]
    if (top && top.score > 0) {
      lines.push(
        `The Attention Score (${Number(row.attention_score).toFixed(1)} / 100) is driven most by ${top.name} in the 0.35 / 0.30 / 0.20 / 0.15 mix — not a black-box model.`,
      )
    }
  }

  return lines.length ? lines : ['Nothing in the z-score, volume, or volatility signals stands out versus the 20-day baseline.']
}

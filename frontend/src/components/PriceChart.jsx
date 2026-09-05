import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  useXAxisScale,
  useYAxisScale,
} from 'recharts'
import { formatPrice, formatVolume } from '../format.js'

function chartLabel(bar, range) {
  const ts = new Date(bar.timestamp)
  if (Number.isNaN(ts.getTime())) return bar.date
  if (range === '1D') {
    return ts.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  }
  if (range === '1Y') {
    return ts.toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
  }
  return ts.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function CandleLayer({ data }) {
  const xScale = useXAxisScale()
  const yScale = useYAxisScale()
  if (!xScale || !yScale || !data?.length) return null

  const slot =
    data.length > 1
      ? Math.abs((xScale(1) ?? 0) - (xScale(0) ?? 0))
      : 12
  const bodyWidth = Math.max(3, Math.min(12, slot * 0.55))

  return (
    <g className="recharts-candlesticks">
      {data.map((bar) => {
        const x = xScale(bar.i)
        const highY = yScale(bar.high)
        const lowY = yScale(bar.low)
        const openY = yScale(bar.open)
        const closeY = yScale(bar.close)
        if ([x, highY, lowY, openY, closeY].some((value) => value == null)) return null
        const up = bar.close >= bar.open
        const color = up ? '#047857' : '#b91c1c'
        const top = Math.min(openY, closeY)
        const height = Math.max(1, Math.abs(closeY - openY))
        return (
          <g key={bar.timestamp ?? bar.i}>
            <line x1={x} x2={x} y1={highY} y2={lowY} stroke={color} strokeWidth={1} />
            <rect x={x - bodyWidth / 2} y={top} width={bodyWidth} height={height} fill={color} />
          </g>
        )
      })}
    </g>
  )
}

function ChartTooltip({ active, payload, chartType }) {
  if (!active || !payload?.length) return null
  const bar = payload[0].payload
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs shadow-sm">
      <p className="font-medium text-zinc-700">{bar.fullLabel}</p>
      {chartType === 'candle' ? (
        <dl className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-zinc-600">
          <dt>O</dt>
          <dd>{formatPrice(bar.open, currency)}</dd>
          <dt>H</dt>
          <dd>{formatPrice(bar.high, currency)}</dd>
          <dt>L</dt>
          <dd>{formatPrice(bar.low, currency)}</dd>
          <dt>C</dt>
          <dd>{formatPrice(bar.close, currency)}</dd>
        </dl>
      ) : (
        <p className="mt-1 font-mono text-zinc-800">{formatPrice(bar.close, currency)}</p>
      )}
      <p className="mt-1 text-zinc-500">Vol {formatVolume(bar.volume)}</p>
    </div>
  )
}

export default function PriceChart({ bars, range, chartType, currency = 'USD' }) {
  const data = (bars ?? []).map((bar, i) => {
    const ts = new Date(bar.timestamp)
    const fullLabel = Number.isNaN(ts.getTime())
      ? bar.date
      : ts.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
    return {
      ...bar,
      i,
      label: chartLabel(bar, range),
      fullLabel,
    }
  })

  if (!data.length) {
    return (
      <div className="flex h-80 items-center justify-center rounded-xl border border-dashed border-zinc-200 bg-zinc-50 text-sm text-zinc-500">
        No bars for this range.
      </div>
    )
  }

  const lows = data.map((bar) => bar.low)
  const highs = data.map((bar) => bar.high)
  const min = Math.min(...lows)
  const max = Math.max(...highs)
  const pad = (max - min) * 0.04 || 1
  const minY = min - pad
  const maxY = max + pad

  const tickEvery = Math.max(1, Math.ceil(data.length / 6))

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#e4e4e7" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="i"
            type="number"
            domain={[0, data.length - 1]}
            interval={tickEvery - 1}
            tickFormatter={(value) => data[value]?.label ?? ''}
            tick={{ fill: '#71717a', fontSize: 11 }}
            axisLine={{ stroke: '#e4e4e7' }}
            tickLine={false}
          />
          <YAxis
            domain={[minY, maxY]}
            width={64}
            tick={{ fill: '#71717a', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) =>
              Number(value).toLocaleString('en-US', { maximumFractionDigits: 0 })
            }
          />
          <Tooltip content={<ChartTooltip chartType={chartType} />} />
          <Line
            type="monotone"
            dataKey="close"
            stroke={chartType === 'line' ? '#18181b' : 'transparent'}
            strokeWidth={chartType === 'line' ? 2 : 0}
            dot={false}
            activeDot={chartType === 'line'}
            isAnimationActive={false}
            legendType="none"
          />
          {chartType === 'candle' ? <CandleLayer data={data} /> : null}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

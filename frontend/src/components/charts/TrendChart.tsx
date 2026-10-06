import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtLong, fmtShort, parseISO, toISO } from '@/lib/dates'
import { capitalize, fmt } from '@/lib/format'
import { AXIS_TICK, GRID_STROKE, TooltipCard, TooltipRow } from './ChartTooltip'

export interface TrendPoint {
  date: string
  value: number
}

interface Props {
  points: TrendPoint[]
  label: string
  unit: string
  /** Color de la serie (un token CSS). */
  color?: string
  decimals?: number
  height?: number
}

interface Point extends TrendPoint {
  time: number
}

function TrendTooltip({ active, payload, label, unit, decimals }: { active?: boolean; payload?: { payload: Point }[]; label: string; unit: string; decimals: number }) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  return (
    <TooltipCard title={capitalize(fmtLong(point.date))}>
      <TooltipRow label={label} value={`${fmt(point.value, decimals)} ${unit}`} />
    </TooltipCard>
  )
}

/** Evolución de un solo valor en el tiempo (una medida, el 1RM estimado de un ejercicio...). */
export default function TrendChart({ points, label, unit, color = 'var(--accent)', decimals = 1, height = 200 }: Props) {
  const data: Point[] = points.map((p) => ({ ...p, time: parseISO(p.date).getTime() }))
  if (!data.length) return null
  const values = data.map((d) => d.value)
  const pad = Math.max(0.5, (Math.max(...values) - Math.min(...values)) * 0.15)
  const low = Math.floor(Math.min(...values) - pad)
  const high = Math.ceil(Math.max(...values) + pad)
  const single = data.length === 1
  const domain: [number, number] = single ? [data[0].time - 3 * 86_400_000, data[0].time + 3 * 86_400_000] : [data[0].time, data[data.length - 1].time]
  return (
    <div style={{ height }} role="img" aria-label={`Gráfica de ${label.toLowerCase()}: ${data.length} registros, el último ${fmt(values[values.length - 1], decimals)} ${unit}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 10, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID_STROKE} />
          <XAxis
            dataKey="time"
            type="number"
            scale="time"
            domain={domain}
            tickLine={false}
            axisLine={{ stroke: GRID_STROKE }}
            tick={AXIS_TICK}
            tickCount={5}
            minTickGap={36}
            tickFormatter={(time: number) => fmtShort(toISO(new Date(time)))}
          />
          <YAxis tickLine={false} axisLine={false} tick={AXIS_TICK} domain={[low, high]} width={38} tickFormatter={(value: number) => fmt(value)} />
          <Tooltip content={<TrendTooltip label={label} unit={unit} decimals={decimals} />} cursor={{ stroke: 'var(--border-strong)', strokeWidth: 1 }} isAnimationActive={false} />
          <Line
            dataKey="value"
            type="monotone"
            stroke={color}
            strokeWidth={2}
            dot={{ r: 3.5, fill: color, stroke: 'var(--surface)', strokeWidth: 2 }}
            activeDot={{ r: 5, fill: color, stroke: 'var(--surface)', strokeWidth: 2 }}
            // Sin animación de entrada: con la carga diferida, recharts dejaba la línea a medio dibujar.
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

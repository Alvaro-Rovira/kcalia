import { useReducedMotion } from 'motion/react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtLong, fmtShort, parseISO } from '@/lib/dates'
import { capitalize, fmt } from '@/lib/format'
import type { WeightPoint } from '@/lib/types'
import { AXIS_TICK, GRID_STROKE, LegendItem, TooltipCard, TooltipRow } from './ChartTooltip'

interface Point extends WeightPoint {
  time: number
}

function WeightTooltip({ active, payload, unit }: { active?: boolean; payload?: { payload: Point }[]; unit: string }) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  return (
    <TooltipCard title={capitalize(fmtLong(point.date))}>
      <TooltipRow color="var(--kcal)" label="Media de 7 días" value={`${fmt(point.avg, 1)} ${unit}`} />
      <TooltipRow color="var(--text-3)" label="Pesada" value={`${fmt(point.kg, 1)} ${unit}`} />
    </TooltipCard>
  )
}

interface Props {
  entries: WeightPoint[]
  target: number | null
  unit: string
  /** Convierte kg a la unidad mostrada. */
  convert: (kg: number) => number
  height?: number
}

/** Pesadas diarias (puntos) y su media móvil de 7 días (línea), que es la que cuenta. */
export default function WeightChart({ entries, target, unit, convert, height = 230 }: Props) {
  const reduce = useReducedMotion()
  const data: Point[] = entries.map((e) => ({ ...e, kg: convert(e.kg), avg: convert(e.avg), time: parseISO(e.date).getTime() }))
  const goal = target === null ? null : convert(target)
  const values = data.flatMap((d) => [d.kg, d.avg])
  if (goal !== null) values.push(goal)
  const low = Math.floor(Math.min(...values) - 0.6)
  const high = Math.ceil(Math.max(...values) + 0.6)
  const span = high - low
  const step = span <= 4 ? 1 : span <= 10 ? 2 : span <= 25 ? 5 : 10
  const ticks: number[] = []
  for (let tick = Math.ceil(low / step) * step; tick <= high; tick += step) ticks.push(tick)
  const single = data.length === 1
  const domain: [number, number] = single
    ? [data[0].time - 3 * 86_400_000, data[0].time + 3 * 86_400_000]
    : [data[0].time, data[data.length - 1].time]

  return (
    <figure>
      <div style={{ height }} role="img" aria-label="Gráfica de peso con media móvil de 7 días">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 10, bottom: 0, left: -22 }}>
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
              tickFormatter={(time: number) => {
                const d = new Date(time)
                return fmtShort(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
              }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={AXIS_TICK}
              domain={[low, high]}
              ticks={ticks}
              width={52}
              tickFormatter={(value: number) => fmt(value)}
            />
            <Tooltip content={<WeightTooltip unit={unit} />} cursor={{ stroke: 'var(--border-strong)', strokeWidth: 1 }} isAnimationActive={false} />
            {goal !== null && (
              <ReferenceLine
                y={goal}
                stroke="var(--text-2)"
                strokeWidth={1}
                label={{ value: `Objetivo ${fmt(goal, Number.isInteger(goal) ? 0 : 1)}`, position: 'insideBottomRight', fill: 'var(--text-2)', fontSize: 11.5 }}
              />
            )}
            <Line
              dataKey="kg"
              stroke="none"
              dot={{ r: 3.5, fill: 'var(--text-3)', stroke: 'var(--surface)', strokeWidth: 2 }}
              activeDot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="avg"
              type="monotone"
              stroke="var(--kcal)"
              strokeWidth={2}
              strokeLinecap="round"
              dot={single ? { r: 4, fill: 'var(--kcal)', stroke: 'var(--surface)', strokeWidth: 2 } : false}
              activeDot={{ r: 5, fill: 'var(--kcal)', stroke: 'var(--surface)', strokeWidth: 2 }}
              isAnimationActive={!reduce}
              animationDuration={900}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        <LegendItem color="var(--kcal)" label="Media móvil de 7 días" shape="line" />
        <LegendItem color="var(--text-3)" label="Pesada del día" shape="dot" />
      </figcaption>
    </figure>
  )
}

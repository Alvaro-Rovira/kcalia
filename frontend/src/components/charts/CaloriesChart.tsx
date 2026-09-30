import { useReducedMotion } from 'motion/react'
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtLong, parseISO, weekdayInitial } from '@/lib/dates'
import { capitalize, fmt, fmtSigned } from '@/lib/format'
import { GRAM_MACROS } from '@/lib/macros'
import type { DayStatus, Macros } from '@/lib/types'
import { AXIS_TICK, GRID_STROKE, LegendItem, TooltipCard, TooltipRow } from './ChartTooltip'

export interface CaloriesPoint extends Macros {
  date: string
  logged: boolean
  status: DayStatus
}

const COLOR: Record<DayStatus, string> = {
  cumplido: 'var(--kcal)',
  bajo: 'var(--text-3)',
  pasado: 'var(--kcal-over)',
  sin_registro: 'transparent',
}

function DayTooltip({ active, payload, target }: { active?: boolean; payload?: { payload: CaloriesPoint }[]; target: number }) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  return (
    <TooltipCard title={capitalize(fmtLong(point.date))}>
      {point.logged ? (
        <>
          <TooltipRow color={COLOR[point.status]} label="Calorías" value={`${fmt(point.kcal)} kcal`} />
          <TooltipRow label="Frente al objetivo" value={`${fmtSigned(point.kcal - target)} kcal`} />
          {GRAM_MACROS.map((m) => (
            <TooltipRow key={m.key} color={m.color} label={m.label} value={`${fmt(point[m.key])} g`} />
          ))}
        </>
      ) : (
        <p className="text-[13px] text-text-3">Sin registros</p>
      )}
    </TooltipCard>
  )
}

/** Calorías por día frente al objetivo. El color del día dice si se cumplió, faltó o sobró. */
export default function CaloriesChart({ data, target, height = 210 }: { data: CaloriesPoint[]; target: number; height?: number }) {
  const reduce = useReducedMotion()
  const dense = data.length > 14
  const max = Math.max(target * 1.2, ...data.map((d) => d.kcal))
  const step = max > 3200 ? 1000 : 500
  const top = Math.ceil(max / step) * step
  const ticks = Array.from({ length: top / step + 1 }, (_, i) => i * step)

  return (
    <figure>
      <div style={{ height }} role="img" aria-label={`Gráfica de calorías por día. Objetivo: ${fmt(target)} kilocalorías.`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 14, right: 4, bottom: 0, left: 0 }} barCategoryGap="22%">
            <CartesianGrid vertical={false} stroke={GRID_STROKE} />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={{ stroke: GRID_STROKE }}
              tick={AXIS_TICK}
              interval={dense ? 'preserveStartEnd' : 0}
              minTickGap={dense ? 18 : 0}
              tickFormatter={(iso: string) => (dense ? String(parseISO(iso).getDate()) : weekdayInitial(iso))}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={AXIS_TICK}
              ticks={ticks}
              domain={[0, top]}
              width={44}
              tickFormatter={(value: number) => fmt(value)}
            />
            <Tooltip content={<DayTooltip target={target} />} cursor={{ fill: 'var(--track)', radius: 6 }} isAnimationActive={false} />
            <Bar dataKey="kcal" maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={!reduce} animationDuration={700} animationEasing="ease-out">
              {data.map((point) => (
                <Cell key={point.date} fill={COLOR[point.status]} />
              ))}
            </Bar>
            <ReferenceLine
              y={target}
              stroke="var(--text-2)"
              strokeWidth={1}
              label={{ value: `Objetivo ${fmt(target)}`, position: 'insideTopRight', fill: 'var(--text-2)', fontSize: 11.5, dy: -16 }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        <LegendItem color={COLOR.cumplido} label="En objetivo (±10 %)" />
        <LegendItem color={COLOR.bajo} label="Por debajo" />
        <LegendItem color={COLOR.pasado} label="Por encima" />
      </figcaption>
    </figure>
  )
}

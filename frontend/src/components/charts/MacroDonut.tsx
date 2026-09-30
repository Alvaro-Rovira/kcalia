import { useReducedMotion } from 'motion/react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { fmt } from '@/lib/format'
import { GRAM_MACROS, KCAL_PER_GRAM, macroSplit } from '@/lib/macros'
import type { Macros } from '@/lib/types'
import { TooltipCard, TooltipRow } from './ChartTooltip'

interface Slice {
  key: 'protein' | 'carbs' | 'fat'
  label: string
  color: string
  grams: number
  kcal: number
  share: number
}

function SliceTooltip({ active, payload }: { active?: boolean; payload?: { payload: Slice }[] }) {
  const slice = payload?.[0]?.payload
  if (!active || !slice) return null
  return (
    <TooltipCard title={slice.label}>
      <TooltipRow color={slice.color} label="De las calorías" value={`${fmt(slice.share * 100)} %`} />
      <TooltipRow label="Media diaria" value={`${fmt(slice.grams)} g`} />
    </TooltipCard>
  )
}

/** Reparto medio de las calorías entre proteínas, hidratos y grasas. */
export default function MacroDonut({ average, targets }: { average: Macros; targets: Macros }) {
  const reduce = useReducedMotion()
  const split = macroSplit(average)
  const targetSplit = macroSplit(targets)
  const slices: Slice[] = GRAM_MACROS.map((m) => {
    const key = m.key as Slice['key']
    return { key, label: m.label, color: m.color, grams: average[key], kcal: average[key] * KCAL_PER_GRAM[key], share: split[key] }
  })
  const empty = slices.every((s) => s.kcal === 0)

  return (
    <div className="flex items-center gap-5">
      <div className="relative size-[132px] shrink-0" role="img" aria-label="Donut con el reparto de macros">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            {!empty && <Tooltip content={<SliceTooltip />} isAnimationActive={false} />}
            <Pie
              data={empty ? [{ key: 'none', kcal: 1 }] : slices}
              dataKey="kcal"
              innerRadius={44}
              outerRadius={64}
              startAngle={90}
              endAngle={-270}
              paddingAngle={empty ? 0 : 3}
              cornerRadius={4}
              stroke="none"
              isAnimationActive={!reduce}
              animationDuration={800}
            >
              {empty ? <Cell fill="var(--track)" /> : slices.map((slice) => <Cell key={slice.key} fill={slice.color} />)}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div>
            <p className="text-[19px] leading-none font-semibold tracking-[-0.02em] text-text" data-num>
              {fmt(average.kcal)}
            </p>
            <p className="mt-1 text-[11px] text-text-3">kcal/día</p>
          </div>
        </div>
      </div>
      <table className="min-w-0 flex-1 text-[13.5px]">
        <caption className="sr-only">Reparto medio de macros frente al objetivo</caption>
        <thead>
          <tr className="text-[11.5px] text-text-3">
            <th scope="col" className="pb-1.5 text-left font-medium">
              Macro
            </th>
            <th scope="col" className="pb-1.5 text-right font-medium">
              Media
            </th>
            <th scope="col" className="pb-1.5 text-right font-medium">
              Plan
            </th>
          </tr>
        </thead>
        <tbody>
          {slices.map((slice) => (
            <tr key={slice.key} className="border-t border-border">
              <th scope="row" className="py-2 text-left font-medium text-text">
                <span className="flex items-center gap-2">
                  <span className="size-2.5 shrink-0 rounded-[3px]" style={{ background: slice.color }} aria-hidden />
                  {slice.label}
                </span>
              </th>
              <td className="py-2 text-right font-semibold text-text" data-num>
                {fmt(slice.share * 100)} %
              </td>
              <td className="py-2 text-right text-text-3" data-num>
                {fmt(targetSplit[slice.key] * 100)} %
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

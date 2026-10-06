import clsx from 'clsx'
import { motion, useReducedMotion } from 'motion/react'
import { Droplets, Plus } from 'lucide-react'
import { useState } from 'react'
import { useBootstrap, useWater, useWaterActions } from '@/hooks/data'
import { haptic } from '@/lib/haptics'
import { fmtWater, WATER_QUICK } from '@/lib/water'
import { NumberInput } from '@/ui/Field'
import { toast } from '@/ui/toast'

/** Agua del día: barra de progreso y botones rápidos. Funciona sin conexión (cola offline). */
export function WaterCard({ date }: { date: string }) {
  const water = useWater(date)
  const actions = useWaterActions()
  const reduce = useReducedMotion()
  const { data: bootstrap } = useBootstrap()
  const [custom, setCustom] = useState<number | null>(null)
  const [editing, setEditing] = useState(false)
  const total = water.data?.total_ml ?? 0
  const goal = bootstrap?.water_goal_ml ?? water.data?.goal_ml ?? 2000
  const ratio = Math.min(1, total / goal)

  function add(ml: number) {
    if (!(ml > 0) || ml > 3000) return
    const entry = actions.add(date, ml)
    haptic('tap')
    toast({ title: `+${fmtWater(ml)} de agua`, action: { label: 'Deshacer', onClick: () => actions.remove(date, entry.client_id) } })
    if (total < goal && total + ml >= goal) toast({ tone: 'success', title: 'Objetivo de agua cumplido', description: fmtWater(goal) })
  }

  return (
    <section className="card mt-3 p-4" aria-label="Agua">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text">
          <Droplets className="size-[18px] text-info-text" aria-hidden />
          Agua
        </h2>
        <p className="text-[14px] text-text-2" data-num>
          <span className="font-semibold text-text">{fmtWater(total)}</span> de {fmtWater(goal)}
        </p>
      </div>
      <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-track" role="meter" aria-valuemin={0} aria-valuemax={goal} aria-valuenow={total} aria-label={`Agua: ${fmtWater(total)} de ${fmtWater(goal)}`}>
        <motion.div className="h-full rounded-full bg-info" initial={false} animate={{ width: `${ratio * 100}%` }} transition={reduce ? { duration: 0 } : { duration: 0.5, ease: [0.22, 1, 0.36, 1] }} />
      </div>
      <div className="mt-3 flex gap-2">
        {WATER_QUICK.map((ml) => (
          <button
            key={ml}
            type="button"
            onClick={() => add(ml)}
            className="flex h-11 flex-1 items-center justify-center gap-1 rounded-full border border-border bg-surface-2 text-[14px] font-semibold text-text active:scale-95"
            aria-label={`Añadir ${ml} ml de agua`}
          >
            <Plus className="size-4 text-info-text" aria-hidden />
            {ml}
          </button>
        ))}
        {editing ? (
          <form
            className="flex h-11 flex-[1.4] items-center gap-1 rounded-full border border-info bg-surface-2 pr-1 pl-3"
            onSubmit={(event) => {
              event.preventDefault()
              if (custom) add(custom)
              setEditing(false)
              setCustom(null)
            }}
          >
            <NumberInput value={custom} onChange={setCustom} decimals={0} min={10} max={3000} ariaLabel="Mililitros de agua" placeholder="ml" autoFocus className="w-full min-w-0 text-[15px] text-text" />
            <button type="submit" className="grid size-9 shrink-0 place-items-center rounded-full bg-info text-bg" aria-label="Añadir esa cantidad">
              <Plus className="size-4" aria-hidden />
            </button>
          </form>
        ) : (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className={clsx('flex h-11 flex-1 items-center justify-center rounded-full border border-dashed border-border-strong text-[14px] font-medium text-text-2')}
          >
            Otra
          </button>
        )}
      </div>
    </section>
  )
}

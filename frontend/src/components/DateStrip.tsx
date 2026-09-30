import clsx from 'clsx'
import { motion } from 'motion/react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useDays } from '@/hooks/data'
import { addDays, fmtLong, parseISO, todayISO, weekdayInitial, weekStart } from '@/lib/dates'
import { haptic } from '@/lib/haptics'
import type { DayStatus } from '@/lib/types'

interface Props {
  date: string
  onChange: (date: string) => void
  targetKcal: number
}

function statusOf(kcal: number, target: number): DayStatus {
  if (kcal < target * 0.9) return 'bajo'
  if (kcal > target * 1.1) return 'pasado'
  return 'cumplido'
}

const DOT: Record<DayStatus, string> = {
  cumplido: 'bg-kcal',
  bajo: 'bg-text-3',
  pasado: 'bg-danger',
  sin_registro: 'bg-transparent',
}
const STATUS_TEXT: Record<DayStatus, string> = {
  cumplido: 'objetivo cumplido',
  bajo: 'por debajo del objetivo',
  pasado: 'por encima del objetivo',
  sin_registro: 'sin registros',
}

/** Semana de lunes a domingo; desliza o usa las flechas para cambiar de semana. */
export function DateStrip({ date, onChange, targetKcal }: Props) {
  const today = todayISO()
  const start = weekStart(date)
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i))
  const { data } = useDays(start, days[6])
  const byDate = new Map((data ?? []).map((d) => [d.date, d]))
  const canGoForward = addDays(start, 7) <= today

  const shift = (weeks: number) => {
    const next = addDays(date, weeks * 7)
    haptic('select')
    onChange(next > today ? today : next)
  }

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => shift(-1)}
        aria-label="Semana anterior"
        className="-ml-2 grid size-11 shrink-0 place-items-center rounded-full text-text-3 hover:text-text"
      >
        <ChevronLeft className="size-5" aria-hidden />
      </button>
      <motion.ul
        className="grid min-w-0 flex-1 grid-cols-7"
        drag="x"
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.25}
        dragSnapToOrigin
        onDragEnd={(_, info) => {
          if (info.offset.x > 60) shift(-1)
          else if (info.offset.x < -60 && canGoForward) shift(1)
        }}
      >
        {days.map((day) => {
          const selected = day === date
          const future = day > today
          const total = byDate.get(day)
          const status: DayStatus = total && total.meals > 0 ? statusOf(total.kcal, targetKcal) : 'sin_registro'
          return (
            <li key={day} className="flex justify-center">
              <button
                type="button"
                disabled={future}
                onClick={() => {
                  if (!selected) {
                    haptic('select')
                    onChange(day)
                  }
                }}
                aria-current={selected ? 'date' : undefined}
                className="relative flex h-[62px] w-full max-w-[46px] flex-col items-center justify-center gap-1 rounded-md disabled:opacity-30"
              >
                {selected && (
                  <motion.span
                    layoutId="day-pill"
                    className="absolute inset-0 rounded-md bg-surface-2 ring-1 ring-border-strong"
                    transition={{ type: 'spring', stiffness: 520, damping: 40 }}
                  />
                )}
                <span className={clsx('relative text-[11px] font-semibold', selected ? 'text-text-2' : 'text-text-3')}>
                  {weekdayInitial(day)}
                </span>
                <span
                  data-num
                  className={clsx(
                    'relative text-[16px] leading-none font-semibold',
                    selected ? 'text-text' : day === today ? 'text-accent-text' : 'text-text-2',
                  )}
                >
                  {parseISO(day).getDate()}
                </span>
                <span className={clsx('relative size-1.5 rounded-full', DOT[status])} aria-hidden />
                {/* El nombre accesible empieza por lo que se ve ("L 28") y añade la fecha completa y el estado. */}
                <span className="sr-only">
                  , {fmtLong(day)}
                  {day === today ? ', hoy' : ''}, {STATUS_TEXT[status]}
                </span>
              </button>
            </li>
          )
        })}
      </motion.ul>
      <button
        type="button"
        onClick={() => shift(1)}
        disabled={!canGoForward}
        aria-label="Semana siguiente"
        className="-mr-2 grid size-11 shrink-0 place-items-center rounded-full text-text-3 hover:text-text disabled:opacity-25"
      >
        <ChevronRight className="size-5" aria-hidden />
      </button>
    </div>
  )
}

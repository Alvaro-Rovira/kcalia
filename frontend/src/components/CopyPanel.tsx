import clsx from 'clsx'
import { CalendarDays, Copy } from 'lucide-react'
import { useState } from 'react'
import { addDays, relativeDay, todayISO } from '@/lib/dates'
import { capitalize, fmt, plural } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import type { Slot } from '@/lib/types'
import { Button } from '@/ui/Button'
import { SlotPicker } from './MealBreakdown'

interface Props {
  /** Día de lo que se copia: no se ofrece como destino rápido. */
  sourceDate: string
  count: number
  kcal: number
  /** Al copiar una comida suelta se puede cambiar el momento; al copiar un día, cada una conserva el suyo. */
  slot?: Slot
  onCopy: (target: { date: string; slot?: Slot }) => void
  onCancel?: () => void
}

/** Elegir a qué día (y momento) copiar. Los destinos rápidos van primero: hoy y ayer. */
export function CopyPanel({ sourceDate, count, kcal, slot: initialSlot, onCopy, onCancel }: Props) {
  const today = todayISO()
  const quick = [today, addDays(today, -1)].filter((d) => d !== sourceDate)
  const [date, setDate] = useState(quick[0] ?? addDays(today, -2))
  const [slot, setSlot] = useState<Slot | undefined>(initialSlot)

  return (
    <div className="space-y-3.5">
      <p className="text-[14px] text-text-2" data-num>
        {count} {plural(count, 'comida', 'comidas')} · {fmt(kcal)} kcal
      </p>
      <div role="radiogroup" aria-label="Día de destino" className="flex flex-wrap gap-2">
        {quick.map((day) => (
          <button
            key={day}
            type="button"
            role="radio"
            aria-checked={date === day}
            onClick={() => {
              haptic('select')
              setDate(day)
            }}
            className={clsx(
              'flex h-11 items-center rounded-full border px-4 text-[14px] font-medium transition-colors',
              date === day ? 'border-accent bg-accent-soft text-accent-text' : 'border-border bg-surface-2 text-text-2',
            )}
          >
            {relativeDay(day)}
          </button>
        ))}
        <label
          className={clsx(
            'relative flex h-11 items-center gap-1.5 rounded-full border px-4 text-[14px] font-medium',
            quick.includes(date) ? 'border-border bg-surface-2 text-text-2' : 'border-accent bg-accent-soft text-accent-text',
          )}
        >
          <CalendarDays className="size-4" aria-hidden />
          {quick.includes(date) ? 'Otro día' : capitalize(relativeDay(date))}
          <input
            type="date"
            value={date}
            max={today}
            onChange={(event) => event.target.value && setDate(event.target.value)}
            aria-label="Elegir otro día"
            className="absolute inset-0 size-full cursor-pointer opacity-0"
          />
        </label>
      </div>
      {slot && (
        <div>
          <span className="eyebrow">Momento del día</span>
          <div className="mt-2">
            <SlotPicker value={slot} onChange={setSlot} />
          </div>
        </div>
      )}
      <div className="flex gap-2">
        {onCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancelar
          </Button>
        )}
        <Button size="sm" className="flex-1" disabled={date === sourceDate && !slot} onClick={() => onCopy({ date, slot })} icon={<Copy className="size-4" aria-hidden />}>
          Copiar a {relativeDay(date).toLowerCase()}
        </Button>
      </div>
    </div>
  )
}

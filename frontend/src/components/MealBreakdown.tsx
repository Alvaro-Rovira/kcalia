import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { Minus, Plus, X } from 'lucide-react'
import { capitalize, fmt, fmtSmart } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { GRAM_MACROS, itemsTotal } from '@/lib/macros'
import { SLOTS } from '@/lib/slots'
import type { Item, Slot } from '@/lib/types'
import { AnimatedNumber } from '@/ui/AnimatedNumber'
import { NumberInput } from '@/ui/Field'
import { MacroBar } from '@/ui/MacroBar'

const PRESETS = [0.5, 1, 1.5, 2]

/** Cambia los gramos de un ingrediente y escala sus macros en proporción. Sin IA. */
function rescale(item: Item, grams: number): Item {
  if (item.grams <= 0 || grams <= 0) return item
  const factor = grams / item.grams
  const round = (n: number) => Math.round(n * factor * 10) / 10
  return {
    ...item,
    grams,
    qty: Math.round(item.qty * factor * 100) / 100,
    kcal: round(item.kcal),
    protein: round(item.protein),
    carbs: round(item.carbs),
    fat: round(item.fat),
  }
}

export function Totals({ items, servings, size = 'lg' }: { items: Item[]; servings: number; size?: 'lg' | 'md' }) {
  const total = itemsTotal(items, servings)
  return (
    <div>
      <div className="flex items-end justify-between gap-4">
        <p className="leading-none">
          <AnimatedNumber
            value={total.kcal}
            from={total.kcal}
            duration={0.5}
            className={clsx('font-semibold tracking-[-0.04em] text-text', size === 'lg' ? 'text-[44px]' : 'text-[34px]')}
          />
          <span className="ml-1.5 text-[15px] font-medium text-text-3">kcal</span>
        </p>
        <dl className="flex gap-4 pb-1">
          {GRAM_MACROS.map((m) => (
            <div key={m.key} className="text-right">
              <dt className="text-[11.5px] font-semibold" style={{ color: m.text }}>
                <span aria-hidden>{m.letter}</span>
                <span className="sr-only">{m.label}</span>
              </dt>
              <dd className="text-[15px] font-semibold text-text">
                <AnimatedNumber value={total[m.key]} from={total[m.key]} duration={0.5} />
                <span className="ml-0.5 text-[12px] font-medium text-text-3">g</span>
              </dd>
            </div>
          ))}
        </dl>
      </div>
      <MacroBar macros={total} height={7} className="mt-3.5" />
    </div>
  )
}

export function ServingsPicker({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  const set = (next: number) => {
    const clamped = Math.min(20, Math.max(0.25, Math.round(next * 100) / 100))
    if (clamped !== value) {
      haptic('select')
      onChange(clamped)
    }
  }
  return (
    <div role="group" aria-label="Raciones">
      <div className="flex items-center justify-between">
        <span className="eyebrow">Raciones</span>
        <span className="text-[13px] text-text-3" data-num>
          ×{fmtSmart(value, 2)}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={() => set(value - 0.25)}
          disabled={value <= 0.25}
          aria-label="Un cuarto de ración menos"
          className="grid size-11 shrink-0 place-items-center rounded-full border border-border bg-surface-2 text-text transition-transform active:scale-90 disabled:opacity-35"
        >
          <Minus className="size-4" aria-hidden />
        </button>
        <div className="grid min-w-0 flex-1 grid-cols-4 gap-1.5">
          {PRESETS.map((preset) => {
            const active = preset === value
            return (
              <button
                key={preset}
                type="button"
                aria-pressed={active}
                onClick={() => set(preset)}
                data-num
                className={clsx(
                  'h-11 rounded-sm border text-[14.5px] font-semibold transition-colors',
                  active ? 'border-accent bg-accent-soft text-accent-text' : 'border-border bg-surface-2 text-text-2',
                )}
              >
                ×{fmtSmart(preset)}
              </button>
            )
          })}
        </div>
        <button
          type="button"
          onClick={() => set(value + 0.25)}
          disabled={value >= 20}
          aria-label="Un cuarto de ración más"
          className="grid size-11 shrink-0 place-items-center rounded-full border border-border bg-surface-2 text-text transition-transform active:scale-90 disabled:opacity-35"
        >
          <Plus className="size-4" aria-hidden />
        </button>
      </div>
    </div>
  )
}

export function ItemList({ items, onChange }: { items: Item[]; onChange?: (items: Item[]) => void }) {
  return (
    <div>
      <span className="eyebrow">Ingredientes</span>
      <ul className="mt-2 overflow-hidden rounded-md border border-border bg-surface">
        <AnimatePresence initial={false}>
          {items.map((item, index) => (
            <motion.li
              key={`${item.name}-${index}`}
              layout
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.22 }}
              className="border-b border-border last:border-b-0"
            >
              <div className="flex items-center gap-2 py-2 pr-1.5 pl-3.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14.5px] font-medium text-text">{capitalize(item.name)}</p>
                  <p className="mt-0.5 text-[12px] text-text-3" data-num>
                    {fmt(item.kcal)} kcal ·{' '}
                    {GRAM_MACROS.map((m, i) => (
                      <span key={m.key}>
                        {i > 0 && ' · '}
                        <span className="font-semibold" style={{ color: m.text }}>
                          {m.letter}
                        </span>{' '}
                        {fmt(item[m.key])}
                      </span>
                    ))}
                  </p>
                </div>
                {onChange ? (
                  <>
                    <label className="flex h-11 shrink-0 items-center gap-1 rounded-sm border border-border bg-surface-2 px-2.5 focus-within:border-accent">
                      <NumberInput
                        value={item.grams}
                        onChange={(grams) => {
                          if (grams && grams > 0) onChange(items.map((it, i) => (i === index ? rescale(it, grams) : it)))
                        }}
                        decimals={0}
                        min={1}
                        max={5000}
                        ariaLabel={`Gramos de ${item.name}`}
                        className="w-[4ch] text-right text-[15px] font-semibold text-text"
                      />
                      <span className="text-[13px] text-text-3">g</span>
                    </label>
                    <button
                      type="button"
                      aria-label={`Quitar ${item.name}`}
                      disabled={items.length === 1}
                      onClick={() => {
                        haptic('tap')
                        onChange(items.filter((_, i) => i !== index))
                      }}
                      className="grid size-11 shrink-0 place-items-center rounded-full text-text-3 hover:text-danger-text disabled:opacity-25"
                    >
                      <X className="size-4" aria-hidden />
                    </button>
                  </>
                ) : (
                  <span className="pr-2.5 text-[13.5px] font-medium text-text-2" data-num>
                    {fmt(item.grams)} g
                  </span>
                )}
              </div>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </div>
  )
}

export function SlotPicker({ value, onChange }: { value: Slot; onChange: (slot: Slot) => void }) {
  return (
    <div role="radiogroup" aria-label="Momento del día" className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5">
      {SLOTS.map(({ key, label, Icon }) => {
        const active = key === value
        return (
          <button
            key={key}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => {
              if (!active) {
                haptic('select')
                onChange(key)
              }
            }}
            className={clsx(
              'flex h-11 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-[14px] font-medium transition-colors',
              active ? 'border-accent bg-accent-soft text-accent-text' : 'border-border bg-surface-2 text-text-2',
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </button>
        )
      })}
    </div>
  )
}

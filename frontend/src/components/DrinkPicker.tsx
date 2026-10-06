import { motion } from 'motion/react'
import { Plus, Wine } from 'lucide-react'
import { useState } from 'react'
import { DRINKS, drinkItem, type Drink } from '@/lib/drinks'
import { fmt } from '@/lib/format'
import { NumberInput } from '@/ui/Field'
import { Button } from '@/ui/Button'

/** Registro rápido de bebidas con alcohol: un toque y se apunta (7 kcal por gramo de alcohol). */
export function DrinkPicker({ onPick }: { onPick: (drink: Drink) => void }) {
  const [custom, setCustom] = useState(false)
  const [ml, setMl] = useState<number | null>(330)
  const [abv, setAbv] = useState<number | null>(5)
  const valid = !!ml && ml > 0 && ml <= 2000 && abv !== null && abv > 0 && abv <= 80
  const preview = valid ? drinkItem({ name: 'Bebida', ml: ml!, abv: abv!, carbs100: 0 }) : null
  return (
    <div className="mt-5">
      <p className="eyebrow">Bebidas con alcohol</p>
      <div className="no-scrollbar -mx-5 mt-2 flex gap-2 overflow-x-auto px-5">
        {DRINKS.map((drink) => (
          <motion.button
            key={drink.key}
            type="button"
            whileTap={{ scale: 0.95 }}
            onClick={() => onPick(drink)}
            aria-label={`Apuntar ${drink.name.toLowerCase()}, ${fmt(drinkItem(drink).kcal)} kilocalorías`}
            className="flex h-11 shrink-0 items-center gap-2 rounded-full border border-border bg-surface-2 pr-3.5 pl-3 text-[14px] font-medium text-text"
          >
            <Wine className="size-3.5 shrink-0 text-text-2" aria-hidden />
            {drink.name}
            <span className="text-[12.5px] text-text-3" data-num>
              {fmt(drinkItem(drink).kcal)}
            </span>
          </motion.button>
        ))}
        <button
          type="button"
          onClick={() => setCustom((v) => !v)}
          aria-expanded={custom}
          className="flex h-11 shrink-0 items-center gap-1.5 rounded-full border border-dashed border-border-strong px-3.5 text-[14px] font-medium text-text-2"
        >
          <Plus className="size-4" aria-hidden />
          Otra
        </button>
      </div>
      {custom && (
        <div className="mt-2.5 flex items-end gap-2 rounded-md border border-border bg-surface p-3">
          <label className="block flex-1">
            <span className="mb-1 block text-[12.5px] text-text-3">Cantidad</span>
            <span className="flex h-11 items-center rounded-sm border border-border bg-surface-2 px-3 focus-within:border-accent">
              <NumberInput value={ml} onChange={setMl} decimals={0} min={10} max={2000} ariaLabel="Mililitros de la bebida" className="min-w-0 flex-1 text-text" />
              <span className="text-[13px] text-text-3">ml</span>
            </span>
          </label>
          <label className="block flex-1">
            <span className="mb-1 block text-[12.5px] text-text-3">Graduación</span>
            <span className="flex h-11 items-center rounded-sm border border-border bg-surface-2 px-3 focus-within:border-accent">
              <NumberInput value={abv} onChange={setAbv} decimals={1} min={0.5} max={80} ariaLabel="Grados de alcohol" className="min-w-0 flex-1 text-text" />
              <span className="text-[13px] text-text-3">% vol</span>
            </span>
          </label>
          <Button
            size="sm"
            disabled={!valid}
            onClick={() => valid && onPick({ key: 'otra', name: `Bebida de ${fmt(ml!)} ml al ${fmt(abv!, 1)} %`, ml: ml!, abv: abv!, carbs100: 0 })}
          >
            <span data-num>{preview ? `${fmt(preview.kcal)} kcal` : 'Añadir'}</span>
          </Button>
        </div>
      )}
    </div>
  )
}

import clsx from 'clsx'
import { motion } from 'motion/react'
import { Plus, Tag } from 'lucide-react'
import { useId, useMemo, useState } from 'react'
import { useBootstrap } from '@/hooks/data'
import { kcalFromMacros, manualItem, manualProblem, searchFoods, type FoodSuggestion } from '@/lib/foods'
import { capitalize, fmt } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { GRAM_MACROS } from '@/lib/macros'
import type { Item } from '@/lib/types'
import { Button } from '@/ui/Button'
import { NumberInput } from '@/ui/Field'
import { Notice } from '@/ui/Notice'
import { Segmented } from '@/ui/Segmented'

type Basis = 'per100' | 'total'

/** Añadir un ingrediente a mano: nombre (con lo que ya conoce la app), gramos y macros. Todo en el móvil, sin IA. */
export function IngredientForm({ onAdd, onCancel }: { onAdd: (item: Item) => void; onCancel: () => void }) {
  const { data } = useBootstrap()
  const id = useId()
  const [name, setName] = useState('')
  const [grams, setGrams] = useState<number | null>(100)
  const [basis, setBasis] = useState<Basis>('per100')
  const [kcal, setKcal] = useState<number | null>(null)
  const [macros, setMacros] = useState<{ protein: number | null; carbs: number | null; fat: number | null }>({ protein: null, carbs: null, fat: null })
  const [picked, setPicked] = useState<FoodSuggestion | null>(null)
  const [error, setError] = useState('')

  const suggestions = useMemo(
    () => (picked ? [] : searchFoods(name, data?.foods ?? [], data?.products ?? [])),
    [name, picked, data?.foods, data?.products],
  )

  function pick(suggestion: FoodSuggestion) {
    haptic('select')
    setPicked(suggestion)
    setName(suggestion.name)
    setBasis('per100')
    setKcal(suggestion.kcal100)
    setMacros({ protein: suggestion.protein100, carbs: suggestion.carbs100, fat: suggestion.fat100 })
    if (suggestion.unitGrams) setGrams(suggestion.unitGrams)
  }

  const input = {
    name,
    grams: grams ?? 0,
    basis,
    kcal,
    protein: macros.protein ?? 0,
    carbs: macros.carbs ?? 0,
    fat: macros.fat ?? 0,
    productId: picked?.productId ?? null,
  }
  const preview = manualProblem(input) ? null : manualItem(input)

  function submit() {
    const problem = manualProblem(input)
    if (problem) {
      haptic('error')
      return setError(problem)
    }
    haptic('success')
    onAdd(manualItem(input))
  }

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.22 }}
      className="overflow-hidden"
    >
      <div className="mt-2.5 space-y-3 rounded-md border border-border bg-surface p-3.5">
        <div className="relative">
          <label htmlFor={`${id}-name`} className="mb-1 block text-[13px] font-medium text-text-2">
            Ingrediente
          </label>
          <input
            id={`${id}-name`}
            value={name}
            onChange={(event) => {
              setName(event.target.value)
              setPicked(null)
              setError('')
            }}
            autoFocus
            autoComplete="off"
            maxLength={120}
            placeholder="Por ejemplo: queso fresco batido"
            role="combobox"
            aria-expanded={suggestions.length > 0}
            aria-controls={`${id}-list`}
            className="h-12 w-full rounded-sm border border-border bg-surface-2 px-3.5 text-text outline-none placeholder:text-text-3 focus:border-accent"
          />
          {suggestions.length > 0 && (
            <ul id={`${id}-list`} role="listbox" aria-label="Ingredientes que ya conozco" className="mt-1.5 overflow-hidden rounded-sm border border-border bg-surface-2">
              {suggestions.map((s) => (
                <li key={s.key} role="option" aria-selected={false} className="border-b border-border last:border-b-0">
                  <button type="button" onClick={() => pick(s)} className="flex min-h-11 w-full items-center gap-2 px-3 py-2 text-left hover:bg-surface-3">
                    {s.productId ? <Tag className="size-3.5 shrink-0 text-accent-text" aria-label="Producto con etiqueta" /> : null}
                    <span className="min-w-0 flex-1 truncate text-[14.5px] text-text">{capitalize(s.name)}</span>
                    <span className="shrink-0 text-[12.5px] text-text-3" data-num>
                      {fmt(s.kcal100)} kcal/100 g
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {picked && <p className="mt-1 text-[12.5px] text-text-3">Con las cifras que ya conocía de «{picked.name}».</p>}
        </div>

        <div className="grid grid-cols-[1fr_auto] items-end gap-2.5">
          <label className="block">
            <span className="mb-1 block text-[13px] font-medium text-text-2">Cantidad</span>
            <span className="flex h-12 items-center rounded-sm border border-border bg-surface-2 px-3.5 focus-within:border-accent">
              <NumberInput value={grams} onChange={setGrams} decimals={0} min={1} max={5000} ariaLabel="Gramos del ingrediente" className="min-w-0 flex-1 text-[16px] text-text" />
              <span className="text-[14px] text-text-3">g</span>
            </span>
          </label>
          <Segmented
            label="Los valores son"
            size="sm"
            className="w-[176px]"
            value={basis}
            onChange={(next) => {
              setBasis(next)
              setPicked((p) => (p ? null : p))
            }}
            options={[
              { value: 'per100', label: 'Por 100 g' },
              { value: 'total', label: 'Total' },
            ]}
          />
        </div>

        <div className="grid grid-cols-4 gap-2">
          <label className="block">
            <span className="mb-1 block text-[12px] font-semibold text-kcal-text">kcal</span>
            <NumberInput
              value={kcal}
              onChange={setKcal}
              decimals={1}
              min={0}
              max={6000}
              ariaLabel="Calorías"
              placeholder={fmt(kcalFromMacros(macros.protein ?? 0, macros.carbs ?? 0, macros.fat ?? 0))}
              className="h-11 w-full rounded-sm border border-border bg-surface-2 px-2 text-center text-[15px] text-text focus:border-accent"
            />
          </label>
          {GRAM_MACROS.map((m) => (
            <label key={m.key} className="block">
              <span className="mb-1 flex items-center gap-1 text-[12px] font-semibold" style={{ color: m.text }}>
                <m.Icon className="size-3" aria-hidden />
                {m.letter}
                <span className="sr-only">{m.label}</span>
              </span>
              <NumberInput
                value={macros[m.key as 'protein' | 'carbs' | 'fat']}
                onChange={(value) => setMacros((old) => ({ ...old, [m.key]: value }))}
                decimals={1}
                min={0}
                max={600}
                ariaLabel={`${m.label} en gramos`}
                placeholder="0"
                className="h-11 w-full rounded-sm border border-border bg-surface-2 px-2 text-center text-[15px] text-text focus:border-accent"
              />
            </label>
          ))}
        </div>
        <p className="text-[12.5px] leading-snug text-text-3">
          {basis === 'per100' ? 'Valores por cada 100 g, como en las etiquetas.' : 'Valores de toda la cantidad indicada.'} Sin calorías, las calculo con los macros.
        </p>

        {error && <Notice level="warn">{error}</Notice>}

        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancelar
          </Button>
          <Button size="sm" className={clsx('flex-1')} onClick={submit} icon={<Plus className="size-4" aria-hidden />}>
            <span data-num>{preview ? `Añadir · ${fmt(preview.kcal)} kcal` : 'Añadir ingrediente'}</span>
          </Button>
        </div>
      </div>
    </motion.div>
  )
}

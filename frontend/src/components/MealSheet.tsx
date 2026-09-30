import { CalendarDays, Copy, Star, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useBootstrap, useDishActions, useMealActions } from '@/hooks/data'
import { relativeDay, todayISO } from '@/lib/dates'
import { capitalize } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import type { Item, Meal, Slot } from '@/lib/types'
import { Button } from '@/ui/Button'
import { Sheet } from '@/ui/Sheet'
import { toast } from '@/ui/toast'
import { ItemList, ServingsPicker, SlotPicker, Totals } from './MealBreakdown'

interface Props {
  meal: Meal | null
  onClose: () => void
  onDelete: (meal: Meal) => void
}

const SOURCE_TEXT: Record<Meal['source'], string> = {
  ai: 'Analizada con IA',
  photo: 'Estimada desde una foto',
  exact: 'De tu historial, sin IA',
  fuzzy: 'De tu historial, sin IA',
  cache: 'Con ingredientes conocidos, sin IA',
  favorite: 'Favorita, sin IA',
  recent: 'Reciente, sin IA',
  manual: 'Añadida a mano',
}

/** Detalle de una comida ya guardada: raciones, momento, día e ingredientes. */
export function MealSheet({ meal, onClose, onDelete }: Props) {
  const actions = useMealActions()
  const dishActions = useDishActions()
  const { data: bootstrap } = useBootstrap()
  const [name, setName] = useState('')
  const [items, setItems] = useState<Item[]>([])
  const [servings, setServings] = useState(1)
  const [slot, setSlot] = useState<Slot>('comida')
  const [date, setDate] = useState(todayISO())
  // Se conserva la última comida para que la hoja no se vacíe mientras se cierra.
  const [shown, setShown] = useState<Meal | null>(null)

  useEffect(() => {
    if (!meal) return
    setShown(meal)
    setName(meal.name)
    setItems(meal.items)
    setServings(meal.servings)
    setSlot(meal.slot)
    setDate(meal.date)
  }, [meal])

  const current = meal ?? shown
  const dish = current?.dish_id ? bootstrap?.dishes.find((d) => d.id === current.dish_id) : undefined
  const today = todayISO()
  const dirty =
    !!current &&
    (name.trim() !== current.name || servings !== current.servings || slot !== current.slot || date !== current.date || items !== current.items)

  function saveChanges() {
    if (!current) return
    actions.update(current, {
      ...(name.trim() && name.trim() !== current.name ? { name: name.trim() } : {}),
      ...(servings !== current.servings ? { servings } : {}),
      ...(slot !== current.slot ? { slot } : {}),
      ...(date !== current.date ? { date } : {}),
      ...(items !== current.items ? { items } : {}),
    })
    haptic('success')
    toast.success('Cambios guardados')
    onClose()
  }

  function duplicate() {
    if (!current) return
    actions.add({
      date: today,
      slot,
      name: current.name,
      text: current.text,
      items,
      servings,
      source: 'recent',
      via: 'tap',
      confidence: current.confidence,
      assumptions: current.assumptions,
      dish_id: current.dish_id,
    })
    haptic('success')
    toast.success(current.date === today ? 'Comida duplicada' : 'Añadida a hoy', 'Sin gastar IA')
    onClose()
  }

  return (
    <Sheet
      open={!!meal}
      onClose={onClose}
      title="Detalle de la comida"
      footer={
        <Button size="lg" block disabled={!dirty} onClick={saveChanges}>
          Guardar cambios
        </Button>
      }
    >
      {current && (
        <div className="space-y-5">
          <div>
            <label htmlFor="edit-name" className="sr-only">
              Nombre de la comida
            </label>
            <input
              id="edit-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={160}
              className="w-full rounded-sm bg-transparent text-[21px] font-semibold tracking-[-0.02em] text-text outline-none focus:bg-surface-2 focus:px-2"
            />
            <p className="mt-1 text-[13px] text-text-3">
              {SOURCE_TEXT[current.source]} · {capitalize(relativeDay(current.date))}
            </p>
          </div>

          <Totals items={items} servings={servings} size="md" />
          <ServingsPicker value={servings} onChange={setServings} />

          <div>
            <span className="eyebrow">Momento del día</span>
            <div className="mt-2">
              <SlotPicker value={slot} onChange={setSlot} />
            </div>
          </div>

          <ItemList items={items} onChange={setItems} />

          <div className="grid grid-cols-2 gap-2.5">
            {dish && (
              <Button
                variant="secondary"
                size="sm"
                aria-pressed={dish.favorite}
                onClick={() => {
                  dishActions.setFavorite(dish, !dish.favorite)
                  toast.success(dish.favorite ? 'Quitada de favoritos' : 'Guardada en favoritos', dish.favorite ? undefined : 'La tendrás a un toque al añadir comida')
                }}
                icon={<Star className={`size-4 ${dish.favorite ? 'fill-carbs text-carbs' : ''}`} aria-hidden />}
              >
                {dish.favorite ? 'Favorita' : 'Favorito'}
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={duplicate} icon={<Copy className="size-4" aria-hidden />}>
              {current.date === today ? 'Duplicar' : 'Repetir hoy'}
            </Button>
            <label className="relative flex h-11 items-center justify-center gap-1.5 rounded-sm border border-border bg-surface-2 px-4 text-[14px] font-semibold text-text focus-within:border-accent">
              <CalendarDays className="size-4" aria-hidden />
              {date === current.date ? 'Cambiar día' : capitalize(relativeDay(date))}
              <input
                type="date"
                value={date}
                max={today}
                onChange={(event) => event.target.value && setDate(event.target.value)}
                aria-label="Mover a otro día"
                className="absolute inset-0 size-full cursor-pointer opacity-0"
              />
            </label>
            <Button
              variant="danger"
              size="sm"
              onClick={() => {
                onDelete(current)
                onClose()
              }}
              icon={<Trash2 className="size-4" aria-hidden />}
            >
              Borrar
            </Button>
          </div>

          {current.assumptions.length > 0 && (
            <p className="text-[13px] leading-relaxed text-text-3">
              <span className="font-semibold text-text-2">Supuestos: </span>
              {current.assumptions.join(' · ')}
            </p>
          )}
        </div>
      )}
    </Sheet>
  )
}

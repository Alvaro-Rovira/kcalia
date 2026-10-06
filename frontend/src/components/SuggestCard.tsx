import { AnimatePresence, motion } from 'motion/react'
import { Check, EyeOff, Plus, RefreshCw, Sparkles, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useApp, useMealActions, useOnline, usePrefsActions } from '@/hooks/data'
import { api, errorMessage } from '@/lib/api'
import { addDays, todayISO } from '@/lib/dates'
import { fmt } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { slotForTime } from '@/lib/slots'
import { buildCandidates, portionLabel, suggest, type Suggestion } from '@/lib/suggest'
import type { DayTargetsValues, Item, Macros, Meal } from '@/lib/types'
import { Button } from '@/ui/Button'
import { MacroInline } from '@/ui/MacroBar'
import { toast } from '@/ui/toast'

interface DayState {
  finished?: boolean
  dismissed?: boolean
  /** Lo que ya se ha enseñado y se ha cambiado por «Otra opción». */
  skipped?: string[]
  shown?: string[]
}

const KEY = (date: string) => `kcalia:cierre:${date}`

function readState(date: string): DayState {
  try {
    return JSON.parse(localStorage.getItem(KEY(date)) ?? '{}') as DayState
  } catch {
    return {}
  }
}

function writeState(date: string, state: DayState) {
  try {
    localStorage.setItem(KEY(date), JSON.stringify(state))
  } catch {
    // Sin almacenamiento, la tarjeta recuerda lo descartado solo mientras está abierta.
  }
}

const minutesOf = (hhmm: string) => {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

interface AiIdea extends Macros {
  name: string
  items: Item[]
}

/** «Te quedan X kcal: ¿qué tal esto?»: cómo cerrar el día sin pasarse, con lo que ya comes. */
export function SuggestCard({ date, eaten, targets, meals }: { date: string; eaten: Macros; targets: DayTargetsValues; meals: Meal[] }) {
  const app = useApp()
  const actions = useMealActions()
  const savePrefs = usePrefsActions()
  const online = useOnline()
  const [state, setState] = useState<DayState>(() => readState(date))
  const [aiIdeas, setAiIdeas] = useState<AiIdea[] | null>(null)
  const [asking, setAsking] = useState(false)
  const prefs = app.prefs ?? { water_goal_ml: null }
  const min = prefs.suggest_min_kcal ?? app.suggest_min_kcal_default ?? 80
  const now = new Date()
  const remaining: Macros = {
    kcal: Math.round((targets.kcal - eaten.kcal) * 10) / 10,
    protein: targets.protein - eaten.protein,
    carbs: targets.carbs - eaten.carbs,
    fat: targets.fat - eaten.fat,
  }
  const triggered =
    !!state.finished || meals.some((m) => m.slot === 'cena') || now.getHours() * 60 + now.getMinutes() >= minutesOf(prefs.suggest_hour ?? '21:00')

  const update = (change: Partial<DayState>) => {
    const next = { ...state, ...change }
    setState(next)
    writeState(date, next)
  }

  const candidates = useMemo(() => buildCandidates({ dishes: app.dishes, products: app.products, foods: app.foods }), [app.dishes, app.products, app.foods])
  const list: Suggestion[] = useMemo(() => {
    if (!triggered || remaining.kcal < min) return []
    const hidden = new Set([...(prefs.suggest_hidden ?? []), ...(state.skipped ?? [])])
    const yesterday = readState(addDays(date, -1)).shown ?? []
    return suggest({ remaining, hour: now.getHours(), candidates, hidden, recent: new Set(yesterday) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggered, remaining.kcal, remaining.protein, min, prefs.suggest_hidden, state.skipped, candidates, date])

  if (prefs.suggest_enabled === false || date !== todayISO() || state.dismissed || remaining.kcal < 0) return null

  if (!triggered) {
    if (!meals.length || remaining.kcal < min) return null
    return (
      <button
        type="button"
        onClick={() => {
          haptic('tap')
          update({ finished: true })
        }}
        className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-dashed border-border-strong px-3 text-[14px] font-medium text-text-2 hover:bg-surface-2"
      >
        <Check className="size-4" aria-hidden /> Ya terminé de comer
      </button>
    )
  }

  if (remaining.kcal < min) {
    return (
      <p className="mt-3 flex items-center gap-2.5 rounded-lg bg-kcal-soft p-3.5 text-[14.5px] text-text">
        <Check className="size-[18px] shrink-0 text-kcal-text" aria-hidden />
        Día redondo: no necesitas nada más.
      </p>
    )
  }

  function add(name: string, items: Item[], dishId: number | null, key: string) {
    const meal = actions.add({
      date,
      slot: slotForTime(),
      name,
      text: '',
      items,
      servings: 1,
      source: 'sugerencia',
      via: 'tap',
      confidence: 0.8,
      assumptions: ['Sugerencia para cerrar el día'],
      dish_id: dishId,
    })
    update({ shown: [...(state.shown ?? []), key] })
    haptic('success')
    toast({ tone: 'success', title: `${name} · ${fmt(meal.kcal)} kcal`, description: 'Añadida a hoy', action: { label: 'Deshacer', onClick: () => actions.remove(meal) } })
  }

  async function askAi() {
    setAsking(true)
    try {
      const { ideas } = await api.post<{ ideas: AiIdea[] }>('/api/suggest/ai', { ...remaining, hour: now.getHours() })
      setAiIdeas(ideas)
      if (!ideas.length) toast({ title: 'La IA no ha encontrado nada que quepa', description: 'Prueba con una de las sugerencias de arriba.' })
    } catch (error) {
      toast.error('No he podido pedir ideas', errorMessage(error))
    } finally {
      setAsking(false)
    }
  }

  const rows = aiIdeas
    ? aiIdeas.map((idea, index) => ({ key: `ai:${index}:${idea.name}`, name: idea.name, detail: 'Idea de la IA', items: idea.items, macros: idea as Macros, dishId: null, proteinCovered: remaining.protein > 0 ? Math.min(1, idea.protein / remaining.protein) : 1, hideable: false }))
    : list.map((s) => ({
        key: s.key,
        name: s.name,
        detail: s.parts.map((p) => portionLabel(p)).join(' + '),
        items: s.items,
        macros: s as Macros,
        dishId: s.dishId,
        proteinCovered: s.proteinCovered,
        hideable: true,
      }))

  return (
    <section className="card mt-3 p-4" aria-label="Sugerencia para cerrar el día">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-[15.5px] font-semibold text-text" data-num>
          Te quedan {fmt(remaining.kcal)} kcal: ¿qué tal esto?
        </h2>
        <button type="button" onClick={() => update({ dismissed: true })} aria-label="Cerrar la sugerencia de hoy" className="-mt-2 -mr-2 grid size-11 shrink-0 place-items-center rounded-full text-text-3 hover:text-text">
          <X className="size-4" aria-hidden />
        </button>
      </div>
      <ul className="mt-2 divide-y divide-border">
        <AnimatePresence initial={false}>
          {rows.map((row) => (
            <motion.li key={row.key} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="py-2.5">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[14.5px] font-medium text-text">{row.name}</p>
                  <p className="mt-0.5 text-[12.5px] text-text-3" data-num>
                    {row.detail} · {fmt(row.macros.kcal)} kcal
                    {remaining.protein > 1 && ` · cubre el ${Math.round(row.proteinCovered * 100)} % de la proteína que falta`}
                  </p>
                  <MacroInline macros={row.macros} className="mt-0.5" />
                </div>
                <Button size="sm" onClick={() => add(row.name, row.items, row.dishId, row.key)} icon={<Plus className="size-4" aria-hidden />} aria-label={`Añadir ${row.name}`}>
                  Añadir
                </Button>
              </div>
              {row.hideable && (
                <button
                  type="button"
                  onClick={() => {
                    savePrefs({ suggest_hidden: [...new Set([...(prefs.suggest_hidden ?? []), ...row.key.split('+')])] })
                    toast({ title: 'No volveré a sugerirlo', description: 'Puedes recuperarlo en Ajustes.' })
                  }}
                  className="mt-1 inline-flex min-h-9 items-center gap-1 text-[12.5px] text-text-3 hover:text-text-2"
                >
                  <EyeOff className="size-3.5" aria-hidden /> No sugerir más esto
                </button>
              )}
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
      <div className="mt-2 flex flex-wrap gap-2">
        {!aiIdeas && rows.length > 0 && (
          <Button variant="secondary" size="sm" onClick={() => update({ skipped: [...(state.skipped ?? []), ...rows.slice(0, 1).flatMap((r) => r.key.split('+'))] })} icon={<RefreshCw className="size-4" aria-hidden />}>
            Otra opción
          </Button>
        )}
        {app.ai.configured && (
          <Button variant="ghost" size="sm" loading={asking} disabled={!online} onClick={() => void askAi()} icon={<Sparkles className="size-4" aria-hidden />}>
            Pedir ideas a la IA
          </Button>
        )}
      </div>
      <p className="mt-2 text-[12px] text-text-3">Son orientaciones, no consejo médico.</p>
    </section>
  )
}

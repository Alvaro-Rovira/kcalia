import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronRight, Plus, Search, Star, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import CaloriesChart, { type CaloriesPoint } from '@/components/charts/CaloriesChart'
import MacroDonut from '@/components/charts/MacroDonut'
import { ItemList, Totals } from '@/components/MealBreakdown'
import { useShell } from '@/components/Shell'
import { useApp, useDays, useDishActions, useMealActions } from '@/hooks/data'
import { errorMessage } from '@/lib/api'
import { addDays, fmtMedium, relativeDay, todayISO } from '@/lib/dates'
import { capitalize, fmt, plural } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { ZERO } from '@/lib/macros'
import { slotForTime } from '@/lib/slots'
import { normalize } from '@/lib/textnorm'
import type { DayStatus, Dish, Macros } from '@/lib/types'
import { keys } from '@/offline/queryClient'
import { Button } from '@/ui/Button'
import { EmptyState } from '@/ui/EmptyState'
import { MacroInline } from '@/ui/MacroBar'
import { Segmented } from '@/ui/Segmented'
import { Sheet } from '@/ui/Sheet'
import { Skeleton } from '@/ui/Skeleton'
import { toast } from '@/ui/toast'

type Range = '7' | '14' | '30'

const STATUS_CHIP: Record<DayStatus, { label: string; className: string }> = {
  cumplido: { label: 'En objetivo', className: 'bg-kcal-soft text-kcal-text' },
  bajo: { label: 'Por debajo', className: 'bg-surface-2 text-text-2' },
  pasado: { label: 'Por encima', className: 'bg-danger-soft text-danger-text' },
  sin_registro: { label: 'Sin registro', className: 'bg-surface-2 text-text-3' },
}

function statusOf(kcal: number, target: number): DayStatus {
  if (kcal < target * 0.9) return 'bajo'
  if (kcal > target * 1.1) return 'pasado'
  return 'cumplido'
}

export default function History() {
  const app = useApp()
  const { targets } = app
  const navigate = useNavigate()
  const [range, setRange] = useState<Range>('7')
  const today = todayISO()
  const start = addDays(today, -(Number(range) - 1))
  const days = useDays(start, today)

  const points: CaloriesPoint[] = useMemo(() => {
    const byDate = new Map((days.data ?? []).map((d) => [d.date, d]))
    return Array.from({ length: Number(range) }, (_, i) => {
      const date = addDays(start, i)
      const day = byDate.get(date)
      const logged = !!day && day.meals > 0
      return {
        date,
        logged,
        kcal: logged ? Math.round(day.kcal) : 0,
        protein: logged ? Math.round(day.protein) : 0,
        carbs: logged ? Math.round(day.carbs) : 0,
        fat: logged ? Math.round(day.fat) : 0,
        status: logged ? statusOf(day.kcal, targets.kcal) : 'sin_registro',
      }
    })
  }, [days.data, range, start, targets.kcal])

  const logged = points.filter((p) => p.logged)
  const average: Macros = logged.length
    ? {
        kcal: logged.reduce((s, p) => s + p.kcal, 0) / logged.length,
        protein: logged.reduce((s, p) => s + p.protein, 0) / logged.length,
        carbs: logged.reduce((s, p) => s + p.carbs, 0) / logged.length,
        fat: logged.reduce((s, p) => s + p.fat, 0) / logged.length,
      }
    : { ...ZERO }

  return (
    <main className="page">
      <header>
        <h1 className="text-[30px] leading-tight font-semibold tracking-[-0.035em] text-text">Historial</h1>
        <p className="mt-1 text-[14.5px] text-text-2">
          {logged.length
            ? `${logged.length} ${plural(logged.length, 'día registrado', 'días registrados')} en los últimos ${range}`
            : `Últimos ${range} días`}
        </p>
      </header>

      <Segmented
        className="mt-4"
        label="Periodo"
        value={range}
        onChange={setRange}
        options={[
          { value: '7', label: '7 días' },
          { value: '14', label: '14 días' },
          { value: '30', label: '30 días' },
        ]}
      />

      <div className="mt-4 grid gap-4 lg:grid-cols-2 lg:items-start">
        <section className="card p-4" aria-labelledby="h-kcal">
          <h2 id="h-kcal" className="text-[15px] font-semibold text-text">
            Calorías por día
          </h2>
          <div className="mt-3">
            {days.isPending ? (
              <Skeleton className="h-[236px]" />
            ) : logged.length === 0 ? (
              <EmptyState art="chart" title="Aún no hay datos" text="Cuando apuntes tus comidas verás aquí cómo van los días." compact />
            ) : (
              <CaloriesChart data={points} target={targets.kcal} />
            )}
          </div>
        </section>

        <section className="card p-4" aria-labelledby="h-split">
          <h2 id="h-split" className="text-[15px] font-semibold text-text">
            Reparto de macros
          </h2>
          <p className="mt-0.5 text-[13px] text-text-3">Media de los días registrados frente a tu plan</p>
          <div className="mt-4">{days.isPending ? <Skeleton className="h-[132px]" /> : <MacroDonut average={average} targets={targets} />}</div>
        </section>
      </div>

      {logged.length > 0 && (
        <section className="mt-6" aria-labelledby="h-days">
          <h2 id="h-days" className="eyebrow">
            Día a día
          </h2>
          <ul className="card mt-2 divide-y divide-border overflow-hidden">
            {[...logged].reverse().map((day, index) => {
              const chip = STATUS_CHIP[day.status]
              return (
                <motion.li key={day.date} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index, 8) * 0.03, duration: 0.3 }}>
                  <button
                    type="button"
                    onClick={() => navigate(day.date === today ? '/' : `/?fecha=${day.date}`)}
                    className="flex min-h-[64px] w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-surface-2"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-[15px] font-medium text-text">{capitalize(day.date === today ? 'Hoy' : relativeDay(day.date))}</p>
                      <MacroInline macros={day} className="mt-1" />
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-[15.5px] font-semibold text-text" data-num>
                        {fmt(day.kcal)} <span className="text-[12px] font-medium text-text-3">kcal</span>
                      </p>
                      <span className={clsx('mt-1 inline-block rounded-full px-2 py-0.5 text-[11.5px] font-semibold', chip.className)}>{chip.label}</span>
                    </div>
                    <ChevronRight className="size-4 shrink-0 text-text-3" aria-hidden />
                  </button>
                </motion.li>
              )
            })}
          </ul>
        </section>
      )}

      <Library dishes={app.dishes} />
    </main>
  )
}

function Library({ dishes }: { dishes: Dish[] }) {
  const [query, setQuery] = useState('')
  const [onlyFavorites, setOnlyFavorites] = useState(false)
  const [selected, setSelected] = useState<Dish | null>(null)
  const [shown, setShown] = useState<Dish | null>(null)
  const dishActions = useDishActions()
  const meals = useMealActions()
  const client = useQueryClient()
  const { openAddMeal } = useShell()

  const filtered = useMemo(() => {
    const words = normalize(query).split(' ').filter(Boolean)
    return dishes
      .filter((d) => (!onlyFavorites || d.favorite) && words.every((w) => d.norm.includes(w) || normalize(d.name).includes(w)))
      .sort((a, b) => Number(b.favorite) - Number(a.favorite) || b.last_used_at.localeCompare(a.last_used_at))
  }, [dishes, query, onlyFavorites])

  const open = (dish: Dish) => {
    setShown(dish)
    setSelected(dish)
  }
  // Se lee de la lista viva para que la estrella refleje el cambio al instante.
  const current = (selected ?? shown) && dishes.find((d) => d.id === (selected ?? shown)!.id)

  function addToday(dish: Dish) {
    const meal = meals.add({
      date: todayISO(),
      slot: slotForTime(),
      name: dish.name,
      text: dish.text,
      items: dish.items,
      servings: 1,
      source: dish.favorite ? 'favorite' : 'recent',
      via: 'tap',
      confidence: dish.confidence,
      assumptions: dish.assumptions,
      dish_id: dish.id,
    })
    haptic('success')
    toast({
      tone: 'success',
      title: `${dish.name} · ${fmt(dish.kcal)} kcal`,
      description: 'Añadida a hoy sin gastar IA',
      action: { label: 'Deshacer', onClick: () => meals.remove(meal) },
    })
    setSelected(null)
  }

  async function remove(dish: Dish) {
    setSelected(null)
    try {
      await dishActions.remove(dish)
      toast.success('Borrada de tu historial', 'Las veces que la apuntaste siguen en el diario.')
    } catch (error) {
      toast.error('No se ha podido borrar', errorMessage(error))
      void client.invalidateQueries({ queryKey: keys.bootstrap })
    }
  }

  return (
    <section className="mt-7" aria-labelledby="h-library">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 id="h-library" className="text-[19px] font-semibold tracking-[-0.02em] text-text">
            Tus comidas
          </h2>
          <p className="mt-0.5 text-[13.5px] text-text-3">Lo que ya conozco: se añade al momento y sin IA.</p>
        </div>
      </div>

      {dishes.length === 0 ? (
        <div className="card mt-3">
          <EmptyState
            art="book"
            title="Tu recetario está vacío"
            text="Cada comida que apuntes se guarda aquí para reutilizarla con un toque."
            action={
              <Button onClick={() => openAddMeal()} icon={<Plus className="size-5" aria-hidden />}>
                Añadir comida
              </Button>
            }
            compact
          />
        </div>
      ) : (
        <>
          <div className="mt-3 flex gap-2">
            <label className="flex h-12 min-w-0 flex-1 items-center gap-2.5 rounded-md border border-border bg-surface-2 px-3.5 focus-within:border-accent">
              <Search className="size-[18px] shrink-0 text-text-3" aria-hidden />
              <span className="sr-only">Buscar en tus comidas</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar en tus comidas"
                enterKeyHint="search"
                className="h-full min-w-0 flex-1 bg-transparent text-text outline-none placeholder:text-text-3"
              />
            </label>
            <button
              type="button"
              aria-pressed={onlyFavorites}
              aria-label="Ver solo favoritas"
              onClick={() => {
                haptic('select')
                setOnlyFavorites((v) => !v)
              }}
              className={clsx(
                'grid size-12 shrink-0 place-items-center rounded-md border transition-colors',
                onlyFavorites ? 'border-carbs bg-carbs-soft' : 'border-border bg-surface-2',
              )}
            >
              <Star className={clsx('size-5', onlyFavorites ? 'fill-carbs text-carbs' : 'text-text-3')} aria-hidden />
            </button>
          </div>

          {filtered.length === 0 ? (
            <p className="py-8 text-center text-[14.5px] text-text-3">
              {onlyFavorites && !query ? 'Aún no tienes favoritas. Marca una con la estrella.' : 'Nada coincide con esa búsqueda.'}
            </p>
          ) : (
            <ul className="card mt-3 divide-y divide-border overflow-hidden">
              <AnimatePresence initial={false}>
                {filtered.slice(0, 60).map((dish) => (
                  <motion.li key={dish.id} layout="position" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center">
                    <button type="button" onClick={() => open(dish)} className="flex min-h-[60px] min-w-0 flex-1 items-center gap-3 py-2.5 pr-1 pl-4 text-left">
                      <div className="min-w-0 flex-1">
                        <p className="flex items-center gap-1.5 text-[15px] font-medium text-text">
                          {dish.favorite && <Star className="size-3.5 shrink-0 fill-carbs text-carbs" aria-label="Favorita" />}
                          <span className="truncate">{dish.name}</span>
                        </p>
                        <p className="mt-1 flex items-center gap-2.5">
                          <MacroInline macros={dish} />
                          <span className="text-[12px] text-text-3" data-num>
                            · {dish.use_count} {plural(dish.use_count, 'vez', 'veces')}
                          </span>
                        </p>
                      </div>
                      <span className="shrink-0 text-[15px] font-semibold text-text" data-num>
                        {fmt(dish.kcal)} <span className="text-[12px] font-medium text-text-3">kcal</span>
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => addToday(dish)}
                      aria-label={`Añadir ${dish.name} a hoy`}
                      className="mr-1.5 grid size-11 shrink-0 place-items-center rounded-full text-accent-text hover:bg-accent-soft"
                    >
                      <Plus className="size-5" aria-hidden />
                    </button>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          )}
        </>
      )}

      <Sheet
        open={!!selected}
        onClose={() => setSelected(null)}
        title={current?.name ?? 'Comida'}
        footer={
          current && (
            <Button size="lg" block onClick={() => addToday(current)} icon={<Plus className="size-5" aria-hidden />}>
              Añadir a hoy
            </Button>
          )
        }
      >
        {current && (
          <div className="space-y-5">
            <p className="text-[13.5px] text-text-3">
              «{current.text}» · usada {current.use_count} {plural(current.use_count, 'vez', 'veces')} · última: {fmtMedium(current.last_used_at.slice(0, 10))}
            </p>
            <Totals items={current.items} servings={1} size="md" />
            <ItemList items={current.items} />
            <div className="grid grid-cols-2 gap-2.5">
              <Button
                variant="secondary"
                size="sm"
                aria-pressed={current.favorite}
                onClick={() => dishActions.setFavorite(current, !current.favorite)}
                icon={<Star className={clsx('size-4', current.favorite && 'fill-carbs text-carbs')} aria-hidden />}
              >
                {current.favorite ? 'Favorita' : 'Favorito'}
              </Button>
              <Button variant="danger" size="sm" onClick={() => void remove(current)} icon={<Trash2 className="size-4" aria-hidden />}>
                Olvidar
              </Button>
            </div>
          </div>
        )}
      </Sheet>
    </section>
  )
}

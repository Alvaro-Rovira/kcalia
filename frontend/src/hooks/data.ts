import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useSyncExternalStore } from 'react'
import { api, newClientId } from '@/lib/api'
import { itemsExtras, itemsTotal } from '@/lib/macros'
import { foodKey } from '@/lib/textnorm'
import { kindFor, targetsFor } from '@/lib/dayTargets'
import { autoWaterGoal } from '@/lib/water'
import type {
  AuthStatus,
  Bootstrap,
  DayKind,
  DayTargetsValues,
  DayTotal,
  Dish,
  FoodEntry,
  Item,
  Meal,
  MealInput,
  Measurement,
  Prefs,
  ProgressPhoto,
  Stats,
  WaterDay,
  WeekSummary,
  WeightData,
} from '@/lib/types'
import { enqueue, outbox, type MealPatch } from '@/offline/outbox'
import { keys } from '@/offline/queryClient'

interface MealsResponse {
  date: string
  meals: Meal[]
}

export function useAuthStatus() {
  // staleTime 0: el estado de sesión guardado nunca se da por bueno sin comprobarlo. Sin red
  // se conserva el guardado, así que el diario sigue viéndose sin conexión.
  return useQuery({ queryKey: keys.auth, queryFn: () => api.get<AuthStatus>('/api/auth/status'), staleTime: 0 })
}

export function useBootstrap(enabled = true) {
  return useQuery({ queryKey: keys.bootstrap, queryFn: () => api.get<Bootstrap>('/api/bootstrap'), enabled })
}

/** Datos de arranque ya cargados. Solo se usa dentro de la app, donde están garantizados. */
export function useApp(): Bootstrap & { profile: NonNullable<Bootstrap['profile']>; targets: NonNullable<Bootstrap['targets']> } {
  const { data } = useBootstrap()
  if (!data?.profile || !data.targets) throw new Error('useApp fuera de la app')
  // La caché guardada en el móvil por una versión anterior no trae los productos hasta que llegan datos nuevos.
  return { ...data, products: data.products ?? [] } as ReturnType<typeof useApp>
}

export function useMeals(date: string) {
  return useQuery({
    queryKey: keys.meals(date),
    queryFn: () => api.get<MealsResponse>(`/api/meals?date=${date}`),
    select: (data) => data.meals,
  })
}

export function useDays(start: string, end: string) {
  return useQuery({
    queryKey: keys.days(start, end),
    queryFn: () => api.get<{ days: DayTotal[] }>(`/api/days?start=${start}&end=${end}`),
    select: (data) => data.days,
  })
}

export function useWeights() {
  return useQuery({ queryKey: keys.weight, queryFn: () => api.get<WeightData>('/api/weight') })
}

export function useWeek(start: string) {
  return useQuery({ queryKey: keys.week(start), queryFn: () => api.get<WeekSummary>(`/api/summary/week?start=${start}`) })
}

export function useSummaries() {
  return useQuery({
    queryKey: keys.summaries,
    queryFn: () => api.get<{ summaries: WeekSummary[] }>('/api/summary/history'),
    select: (data) => data.summaries,
  })
}

export function useStats() {
  return useQuery({ queryKey: keys.stats, queryFn: () => api.get<Stats>('/api/stats') })
}

export function usePendingCount(): number {
  return useSyncExternalStore(outbox.subscribe, outbox.pendingCount)
}

export function useOnline(): boolean {
  return useSyncExternalStore(
    (listener) => {
      window.addEventListener('online', listener)
      window.addEventListener('offline', listener)
      return () => {
        window.removeEventListener('online', listener)
        window.removeEventListener('offline', listener)
      }
    },
    () => navigator.onLine,
  )
}

/** Los ingredientes añadidos a mano ya salen al autocompletar, también sin red (el servidor los aprende al sincronizar). */
function rememberManualFoods(client: ReturnType<typeof useQueryClient>, items: Item[]): void {
  const manual = items.filter((i) => i.manual && !i.product_id && i.grams > 0)
  if (!manual.length) return
  client.setQueryData<Bootstrap>(keys.bootstrap, (old) => {
    if (!old) return old
    const foods = [...(old.foods ?? [])]
    for (const item of manual) {
      const per = (v: number) => Math.round((v / item.grams) * 1000) / 10
      const entry: FoodEntry = {
        name: item.name,
        norm: foodKey(item.name),
        kcal100: per(item.kcal),
        protein100: per(item.protein),
        carbs100: per(item.carbs),
        fat100: per(item.fat),
        unit_grams: {},
      }
      const index = foods.findIndex((f) => f.norm === entry.norm)
      if (index >= 0) foods[index] = { ...foods[index], ...entry, unit_grams: foods[index].unit_grams }
      else foods.unshift(entry)
    }
    return { ...old, foods }
  })
}

/** Escrituras del diario: se reflejan al instante y viajan al servidor por la cola offline. */
export function useMealActions() {
  const client = useQueryClient()

  const patchList = useCallback(
    (date: string, update: (meals: Meal[]) => Meal[]) => {
      client.setQueryData<MealsResponse>(keys.meals(date), (old) => ({ date, meals: update(old?.meals ?? []) }))
    },
    [client],
  )

  const add = useCallback(
    (input: Omit<MealInput, 'client_id'> & { client_id?: string }): Meal => {
      const body: MealInput = { ...input, client_id: input.client_id ?? newClientId() }
      const meal: Meal = {
        id: -Date.now(),
        client_id: body.client_id,
        date: body.date,
        slot: body.slot,
        name: body.name,
        text: body.text,
        items: body.items,
        servings: body.servings,
        source: body.source,
        confidence: body.confidence,
        assumptions: body.assumptions,
        dish_id: body.dish_id,
        created_at: new Date().toISOString(),
        pending: true,
        ...itemsTotal(body.items, body.servings),
        ...itemsExtras(body.items, body.servings),
      }
      patchList(body.date, (meals) => [...meals, meal])
      rememberManualFoods(client, body.items)
      void enqueue({ type: 'meal.create', body })
      return meal
    },
    [patchList, client],
  )

  const remove = useCallback(
    (meal: Meal) => {
      patchList(meal.date, (meals) => meals.filter((m) => m.client_id !== meal.client_id))
      void enqueue({ type: 'meal.delete', clientId: meal.client_id })
    },
    [patchList],
  )

  const restore = useCallback(
    (meal: Meal) => {
      patchList(meal.date, (meals) =>
        meals.some((m) => m.client_id === meal.client_id)
          ? meals
          : [...meals, meal].sort((a, b) => a.created_at.localeCompare(b.created_at)),
      )
      void enqueue({ type: 'meal.restore', clientId: meal.client_id })
    },
    [patchList],
  )

  const update = useCallback(
    (meal: Meal, patch: MealPatch) => {
      const next: Meal = { ...meal, ...patch, pending: true }
      Object.assign(next, itemsTotal(next.items, next.servings), itemsExtras(next.items, next.servings))
      if (patch.date && patch.date !== meal.date) {
        patchList(meal.date, (meals) => meals.filter((m) => m.client_id !== meal.client_id))
        patchList(patch.date, (meals) => [...meals, next])
      } else {
        patchList(meal.date, (meals) => meals.map((m) => (m.client_id === meal.client_id ? next : m)))
      }
      if (patch.items) rememberManualFoods(client, patch.items)
      void enqueue({ type: 'meal.patch', clientId: meal.client_id, body: patch })
    },
    [patchList, client],
  )

  return { add, remove, restore, update }
}

export function useDishActions() {
  const client = useQueryClient()
  const setFavorite = useCallback(
    (dish: Dish, favorite: boolean) => {
      client.setQueryData<Bootstrap>(keys.bootstrap, (old) =>
        old ? { ...old, dishes: old.dishes.map((d) => (d.id === dish.id ? { ...d, favorite } : d)) } : old,
      )
      void enqueue({ type: 'dish.patch', dishId: dish.id, body: { favorite } })
    },
    [client],
  )
  const remove = useCallback(
    async (dish: Dish) => {
      client.setQueryData<Bootstrap>(keys.bootstrap, (old) =>
        old ? { ...old, dishes: old.dishes.filter((d) => d.id !== dish.id) } : old,
      )
      await api.delete(`/api/dishes/${dish.id}`)
    },
    [client],
  )
  return { setFavorite, remove }
}

export function useWeightActions() {
  const client = useQueryClient()
  const save = useCallback(
    (date: string, kg: number) => {
      client.setQueryData<WeightData>(keys.weight, (old) => {
        if (!old) return old
        const others = old.entries.filter((e) => e.date !== date)
        const entries = [...others, { date, kg, avg: kg }].sort((a, b) => a.date.localeCompare(b.date))
        return { ...old, entries }
      })
      void enqueue({ type: 'weight.put', body: { date, kg } })
    },
    [client],
  )
  const remove = useCallback(
    (date: string) => {
      client.setQueryData<WeightData>(keys.weight, (old) =>
        old ? { ...old, entries: old.entries.filter((e) => e.date !== date) } : old,
      )
      void enqueue({ type: 'weight.delete', date })
    },
    [client],
  )
  return { save, remove }
}

export function useWater(date: string) {
  return useQuery({ queryKey: keys.water(date), queryFn: () => api.get<WaterDay>(`/api/water?date=${date}`) })
}

export function useWaterDays(start: string, end: string) {
  return useQuery({
    queryKey: keys.waterDays(start, end),
    queryFn: () => api.get<{ goal_ml: number; days: { date: string; ml: number }[] }>(`/api/water/days?start=${start}&end=${end}`),
  })
}

/** Agua: se suma al instante en pantalla y viaja por la cola offline (cada toque, su propio id). */
export function useWaterActions() {
  const client = useQueryClient()
  const goal = useBootstrap().data?.water_goal_ml ?? 2000
  const patch = useCallback(
    (date: string, update: (day: WaterDay) => WaterDay) => {
      client.setQueryData<WaterDay>(keys.water(date), (old) => {
        const day = update(old ?? { date, total_ml: 0, goal_ml: goal, entries: [] })
        return { ...day, total_ml: day.entries.reduce((sum, e) => sum + e.ml, 0) }
      })
    },
    [client, goal],
  )
  const add = useCallback(
    (date: string, ml: number) => {
      const entry = { client_id: newClientId(), ml, created_at: new Date().toISOString(), pending: true }
      patch(date, (day) => ({ ...day, entries: [...day.entries, entry] }))
      void enqueue({ type: 'water.add', body: { client_id: entry.client_id, date, ml } })
      return entry
    },
    [patch],
  )
  const remove = useCallback(
    (date: string, clientId: string) => {
      patch(date, (day) => ({ ...day, entries: day.entries.filter((e) => e.client_id !== clientId) }))
      void enqueue({ type: 'water.delete', clientId })
    },
    [patch],
  )
  return { add, remove }
}

/** Preferencias: se aplican al momento en los datos del móvil y se guardan por la cola offline. */
export function usePrefsActions() {
  const client = useQueryClient()
  return useCallback(
    (changes: Partial<Prefs>) => {
      client.setQueryData<Bootstrap>(keys.bootstrap, (old) => {
        if (!old) return old
        const prefs = { ...(old.prefs ?? { water_goal_ml: null }), ...changes }
        const water_goal_ml = prefs.water_goal_ml ?? autoWaterGoal(old.profile?.weight_kg)
        return { ...old, prefs, water_goal_ml }
      })
      void enqueue({ type: 'prefs.patch', body: changes })
    },
    [client],
  )
}

export function useMeasurements() {
  return useQuery({
    queryKey: keys.measurements,
    queryFn: () => api.get<{ entries: Measurement[] }>('/api/measurements'),
    select: (data) => data.entries,
  })
}

/** Medidas: un registro por día; se ven al momento y viajan por la cola offline. */
export function useMeasureActions() {
  const client = useQueryClient()
  const set = useCallback(
    (update: (entries: Measurement[]) => Measurement[]) =>
      client.setQueryData<{ entries: Measurement[] }>(keys.measurements, (old) => ({ entries: update(old?.entries ?? []) })),
    [client],
  )
  const save = useCallback(
    (entry: Measurement) => {
      set((entries) => [...entries.filter((e) => e.date !== entry.date), entry].sort((a, b) => a.date.localeCompare(b.date)))
      void enqueue({ type: 'measure.put', body: entry })
    },
    [set],
  )
  const remove = useCallback(
    (date: string) => {
      set((entries) => entries.filter((e) => e.date !== date))
      void enqueue({ type: 'measure.delete', date })
    },
    [set],
  )
  return { save, remove }
}

export function usePhotos() {
  return useQuery({ queryKey: keys.photos, queryFn: () => api.get<{ photos: ProgressPhoto[] }>('/api/photos'), select: (data) => data.photos })
}

/** Objetivos de un día concreto según su tipo (entreno o descanso). Se calcula en el móvil: funciona sin red. */
export function useDayTargets(): (iso: string) => { kind: DayKind | null; targets: DayTargetsValues; manual: boolean } {
  const { data } = useBootstrap()
  return useCallback(
    (iso: string) => {
      const base = data?.targets ?? { kcal: 2000, protein: 120, carbs: 220, fat: 65 }
      const overrides = data?.day_types ?? {}
      const kind = kindFor(iso, data?.prefs, overrides)
      // El entreno sumado al objetivo llega con el registro de entrenos (ver useExerciseKcal).
      return { kind, targets: targetsFor(base, data?.prefs, kind), manual: iso in overrides }
    },
    [data?.targets, data?.day_types, data?.prefs],
  )
}

export function useDayTypeActions() {
  const client = useQueryClient()
  return useCallback(
    (date: string, kind: DayKind | null) => {
      client.setQueryData<Bootstrap>(keys.bootstrap, (old) => {
        if (!old) return old
        const day_types = { ...(old.day_types ?? {}) }
        if (kind) day_types[date] = kind
        else delete day_types[date]
        return { ...old, day_types }
      })
      void enqueue({ type: 'daytype.put', body: { date, kind } })
    },
    [client],
  )
}

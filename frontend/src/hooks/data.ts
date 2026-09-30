import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useSyncExternalStore } from 'react'
import { api, newClientId } from '@/lib/api'
import { itemsTotal } from '@/lib/macros'
import type {
  AuthStatus,
  Bootstrap,
  DayTotal,
  Dish,
  Meal,
  MealInput,
  Stats,
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
  return useQuery({ queryKey: keys.auth, queryFn: () => api.get<AuthStatus>('/api/auth/status'), staleTime: 60_000 })
}

export function useBootstrap(enabled = true) {
  return useQuery({ queryKey: keys.bootstrap, queryFn: () => api.get<Bootstrap>('/api/bootstrap'), enabled })
}

/** Datos de arranque ya cargados. Solo se usa dentro de la app, donde están garantizados. */
export function useApp(): Bootstrap & { profile: NonNullable<Bootstrap['profile']>; targets: NonNullable<Bootstrap['targets']> } {
  const { data } = useBootstrap()
  if (!data?.profile || !data.targets) throw new Error('useApp fuera de la app')
  return data as ReturnType<typeof useApp>
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
      }
      patchList(body.date, (meals) => [...meals, meal])
      void enqueue({ type: 'meal.create', body })
      return meal
    },
    [patchList],
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
      Object.assign(next, itemsTotal(next.items, next.servings))
      if (patch.date && patch.date !== meal.date) {
        patchList(meal.date, (meals) => meals.filter((m) => m.client_id !== meal.client_id))
        patchList(patch.date, (meals) => [...meals, next])
      } else {
        patchList(meal.date, (meals) => meals.map((m) => (m.client_id === meal.client_id ? next : m)))
      }
      void enqueue({ type: 'meal.patch', clientId: meal.client_id, body: patch })
    },
    [patchList],
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

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { api, newClientId } from '@/lib/api'
import { itemsTotal } from '@/lib/macros'
import type { PlanEntry } from '@/lib/shopping'
import type { DayTargetsValues } from '@/lib/types'
import { enqueue } from '@/offline/outbox'
import { keys } from '@/offline/queryClient'

export interface PlanWeek {
  start: string
  end: string
  entries: PlanEntry[]
  targets: Record<string, DayTargetsValues & { kind?: string | null }>
  checks: Record<string, boolean>
}

export function usePlan(start: string) {
  return useQuery({ queryKey: keys.plan(start), queryFn: () => api.get<PlanWeek>(`/api/plan?start=${start}`) })
}

/** Cambios del plan: al momento en pantalla y por la cola offline. */
export function usePlanActions(start: string) {
  const client = useQueryClient()
  const update = useCallback(
    (change: (week: PlanWeek) => PlanWeek) =>
      client.setQueryData<PlanWeek>(keys.plan(start), (old) => change(old ?? { start, end: start, entries: [], targets: {}, checks: {} })),
    [client, start],
  )

  const save = useCallback(
    (input: Omit<PlanEntry, 'client_id' | 'kcal' | 'protein' | 'carbs' | 'fat'> & { client_id?: string }) => {
      const entry: PlanEntry = { ...input, client_id: input.client_id ?? newClientId(), ...itemsTotal(input.items, input.servings), pending: true }
      update((week) => ({
        ...week,
        entries: week.entries.some((e) => e.client_id === entry.client_id)
          ? week.entries.map((e) => (e.client_id === entry.client_id ? entry : e))
          : [...week.entries, entry],
      }))
      const { client_id, date, slot, name, items, servings, dish_id, source } = entry
      void enqueue({ type: 'plan.save', body: { client_id, date, slot, name, items, servings, dish_id, source } })
      return entry
    },
    [update],
  )

  const remove = useCallback(
    (clientId: string) => {
      update((week) => ({ ...week, entries: week.entries.filter((e) => e.client_id !== clientId) }))
      void enqueue({ type: 'plan.delete', clientId })
    },
    [update],
  )

  const check = useCallback(
    (key: string, checked: boolean) => {
      update((week) => ({ ...week, checks: { ...week.checks, [key]: checked } }))
      void enqueue({ type: 'shopping.check', body: { week_start: start, key, checked } })
    },
    [update, start],
  )

  return { save, remove, check }
}

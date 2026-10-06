/**
 * Cola de cambios hechos en el móvil. Cada cambio se aplica al momento en la interfaz
 * y se envía al servidor en orden en cuanto hay red. Las comidas llevan un client_id
 * generado aquí, así que reenviar la misma operación no duplica nada.
 */
import { del, get, set } from 'idb-keyval'
import { api, ApiError } from '@/lib/api'
import type { Item, MealInput, Measurement, Prefs, Slot } from '@/lib/types'

export interface MealPatch {
  date?: string
  slot?: Slot
  name?: string
  items?: Item[]
  servings?: number
}

export type Op =
  | { id: string; type: 'meal.create'; body: MealInput }
  | { id: string; type: 'meal.patch'; clientId: string; body: MealPatch }
  | { id: string; type: 'meal.delete'; clientId: string }
  | { id: string; type: 'meal.restore'; clientId: string }
  | { id: string; type: 'weight.put'; body: { date: string; kg: number } }
  | { id: string; type: 'weight.delete'; date: string }
  | { id: string; type: 'dish.patch'; dishId: number; body: { favorite: boolean } }
  | { id: string; type: 'water.add'; body: { client_id: string; date: string; ml: number } }
  | { id: string; type: 'water.delete'; clientId: string }
  | { id: string; type: 'prefs.patch'; body: Partial<Prefs> }
  | { id: string; type: 'measure.put'; body: Measurement }
  | { id: string; type: 'measure.delete'; date: string }

type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never
export type NewOp = DistributiveOmit<Op, 'id'>

const KEY = 'kcalia:outbox'

let queue: Op[] = []
let loaded = false
let flushing = false
const listeners = new Set<() => void>()
let onSynced: (types: Set<Op['type']>) => void = () => undefined
let onRejected: (op: Op, error: ApiError) => void = () => undefined

function notify(): void {
  for (const listener of listeners) listener()
}

async function persist(): Promise<void> {
  try {
    if (queue.length) await set(KEY, queue)
    else await del(KEY)
  } catch {
    // Sin IndexedDB la cola vive solo en memoria durante esta sesión.
  }
}

async function load(): Promise<void> {
  if (loaded) return
  loaded = true
  try {
    const stored = await get<Op[]>(KEY)
    if (stored?.length) queue = [...stored, ...queue]
  } catch {
    // Igual que arriba.
  }
  notify()
}

function send(op: Op): Promise<unknown> {
  switch (op.type) {
    case 'meal.create':
      return api.post('/api/meals', op.body)
    case 'meal.patch':
      return api.patch(`/api/meals/${op.clientId}`, op.body)
    case 'meal.delete':
      return api.delete(`/api/meals/${op.clientId}`)
    case 'meal.restore':
      return api.post(`/api/meals/${op.clientId}/restore`)
    case 'weight.put':
      return api.put('/api/weight', op.body)
    case 'weight.delete':
      return api.delete(`/api/weight/${op.date}`)
    case 'dish.patch':
      return api.patch(`/api/dishes/${op.dishId}`, op.body)
    case 'water.add':
      return api.post('/api/water', op.body)
    case 'water.delete':
      return api.delete(`/api/water/${op.clientId}`)
    case 'prefs.patch':
      return api.patch('/api/prefs', op.body)
    case 'measure.put':
      return api.put('/api/measurements', op.body)
    case 'measure.delete':
      return api.delete(`/api/measurements/${op.date}`)
  }
}

export async function flush(): Promise<void> {
  await load()
  if (flushing || !queue.length) return
  flushing = true
  const synced = new Set<Op['type']>()
  try {
    while (queue.length) {
      const op = queue[0]
      try {
        await send(op)
        synced.add(op.type)
      } catch (error) {
        const apiError = error instanceof ApiError ? error : new ApiError('', 0)
        // Sin red, sesión caducada, cuenta sin aprobar o servidor caído: se queda en cola y se reintenta.
        const accountBlocked = apiError.status === 403 && !!apiError.code?.startsWith('account_')
        if (apiError.offline || apiError.status === 401 || accountBlocked || apiError.status >= 500) break
        // El servidor lo rechaza de forma definitiva: no tiene sentido insistir.
        onRejected(op, apiError)
        synced.add(op.type)
      }
      queue = queue.slice(1)
      await persist()
      notify()
    }
  } finally {
    flushing = false
    if (synced.size) onSynced(synced)
  }
}

export async function enqueue(op: NewOp): Promise<void> {
  await load()
  const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
  queue = [...queue, { ...op, id } as Op]
  await persist()
  notify()
  void flush()
}

export async function clearOutbox(): Promise<void> {
  queue = []
  await persist()
  notify()
}

export const outbox = {
  subscribe(listener: () => void): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
  pendingCount: () => queue.length,
  init(handlers: { onSynced: typeof onSynced; onRejected: typeof onRejected }): void {
    onSynced = handlers.onSynced
    onRejected = handlers.onRejected
    window.addEventListener('online', () => void flush())
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') void flush()
    })
    void flush()
  },
}

import type { Slot } from './types'

export interface Usage {
  use_count: number
  last_used_at: string
  slot_counts?: Partial<Record<Slot, number>>
}

const DAY = 86_400_000

/**
 * Puntuación de una comida para el momento del día: lo que sueles tomar a esta hora sube, lo que nunca tomas a esta
 * hora baja. Se combinan la afinidad con el momento (suavizada para que una sola vez no lo decida todo), la frecuencia
 * de uso y lo reciente que es.
 */
export function slotScore(entry: Usage, slot: Slot, now = Date.now()): number {
  const counts = entry.slot_counts ?? {}
  const total = Object.values(counts).reduce((sum, n) => sum + (n ?? 0), 0)
  const here = counts[slot] ?? 0
  const affinity = (here + 0.5) / (total + 2.5)
  const frequency = Math.log2(1 + Math.max(entry.use_count, total))
  const last = Date.parse(entry.last_used_at)
  const days = Number.isNaN(last) ? 365 : Math.max(0, (now - last) / DAY)
  const recency = Math.exp(-days / 14)
  return affinity * 4 + frequency * 0.6 + recency
}

/** Ordena para el momento del día (estable: a igualdad, se respeta el orden de entrada). */
export function rankForSlot<T extends Usage>(entries: T[], slot: Slot, now = Date.now()): T[] {
  return entries
    .map((entry, index) => ({ entry, index, score: slotScore(entry, slot, now) }))
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map(({ entry }) => entry)
}

import { Coffee, Cookie, Croissant, Soup, UtensilsCrossed, type LucideIcon } from 'lucide-react'
import type { Slot } from './types'

export const SLOTS: { key: Slot; label: string; Icon: LucideIcon }[] = [
  { key: 'desayuno', label: 'Desayuno', Icon: Coffee },
  { key: 'comida', label: 'Comida', Icon: UtensilsCrossed },
  { key: 'merienda', label: 'Merienda', Icon: Croissant },
  { key: 'cena', label: 'Cena', Icon: Soup },
  { key: 'snack', label: 'Snack', Icon: Cookie },
]

export const SLOT_BY_KEY = Object.fromEntries(SLOTS.map((s) => [s.key, s])) as Record<Slot, (typeof SLOTS)[number]>

/** Momento del día según la hora, con horarios españoles. */
export function slotForTime(now = new Date()): Slot {
  const minutes = now.getHours() * 60 + now.getMinutes()
  if (minutes < 5 * 60) return 'snack'
  if (minutes < 12 * 60) return 'desayuno'
  if (minutes < 16 * 60 + 30) return 'comida'
  if (minutes < 20 * 60) return 'merienda'
  return 'cena'
}

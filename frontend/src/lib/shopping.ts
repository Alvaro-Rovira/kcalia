import { foodKey } from './textnorm'
import type { Item } from './types'

export interface PlanEntry {
  client_id: string
  date: string
  slot: 'desayuno' | 'comida' | 'merienda' | 'cena' | 'snack'
  name: string
  items: Item[]
  servings: number
  dish_id: number | null
  source: 'dish' | 'product' | 'manual' | 'ai'
  kcal: number
  protein: number
  carbs: number
  fat: number
  pending?: boolean
}

export interface ShoppingLine {
  key: string
  name: string
  grams: number
  /** Unidades contadas (huevos, latas, yogures...) si todas las apariciones van en la misma unidad. */
  units: { qty: number; unit: string } | null
  meals: number
}

const MASS_OR_VOLUME = new Set(['g', 'ml', 'kg', 'l'])

/** Lista de la compra: los ingredientes de la semana juntos por alimento, con las raciones ya multiplicadas. */
export function shoppingList(entries: PlanEntry[]): ShoppingLine[] {
  const lines = new Map<string, ShoppingLine & { unitSet: Set<string>; qty: number }>()
  for (const entry of entries) {
    for (const item of entry.items) {
      const key = foodKey(item.name) || item.name.toLowerCase()
      const line = lines.get(key) ?? { key, name: item.name, grams: 0, units: null, meals: 0, unitSet: new Set<string>(), qty: 0 }
      line.grams += (item.grams || 0) * entry.servings
      line.meals += 1
      if (!MASS_OR_VOLUME.has(item.unit)) {
        line.unitSet.add(item.unit)
        line.qty += (item.qty || 0) * entry.servings
      } else line.unitSet.add('peso')
      lines.set(key, line)
    }
  }
  return [...lines.values()]
    .map(({ unitSet, qty, ...line }) => ({
      ...line,
      grams: Math.round(line.grams),
      units: unitSet.size === 1 && !unitSet.has('peso') ? { qty: Math.round(qty * 10) / 10, unit: [...unitSet][0] } : null,
    }))
    .sort((a, b) => a.name.localeCompare(b.name, 'es'))
}

/** «250 g», «1,2 kg». */
export function fmtGrams(grams: number): string {
  if (grams >= 1000) return `${(Math.round(grams / 100) / 10).toLocaleString('es-ES')} kg`
  return `${Math.round(grams)} g`
}

import { newClientId } from './api'
import type { Meal, MealInput, Slot } from './types'

export interface CopyTarget {
  date: string
  /** Solo al copiar una comida suelta; al copiar un día, cada comida conserva su momento. */
  slot?: Slot
}

/**
 * Lo que hay que enviar para copiar comidas: cada copia con su propio client_id, generado una sola vez aquí.
 * Así, reenviar la cola offline no duplica nada y copiar dos veces crea dos copias.
 */
export function copyInputs(meals: Meal[], target: CopyTarget, makeId: () => string = newClientId): MealInput[] {
  return meals.map((meal) => ({
    client_id: makeId(),
    date: target.date,
    slot: target.slot ?? meal.slot,
    name: meal.name,
    text: meal.text,
    items: meal.items.map((item) => ({ ...item, manual: false })),
    servings: meal.servings,
    // Una copia no gasta IA: cuenta como «a un toque», igual que los recientes.
    source: 'recent',
    via: 'tap',
    confidence: meal.confidence,
    assumptions: meal.assumptions,
    dish_id: meal.dish_id,
  }))
}

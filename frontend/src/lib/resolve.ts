import { findSimilar, normalize } from './textnorm'
import type { Dish, Draft, Source } from './types'

export function draftFromDish(dish: Dish, source: Source, text?: string, score?: number): Draft {
  return {
    name: dish.name,
    text: text ?? dish.text,
    items: dish.items,
    kcal: dish.kcal,
    protein: dish.protein,
    carbs: dish.carbs,
    fat: dish.fat,
    confidence: dish.confidence,
    assumptions: dish.assumptions,
    source,
    dish_id: dish.id,
    favorite: dish.favorite,
    score,
    matched_text: dish.text,
  }
}

export type LocalMatch = { status: 'exact'; draft: Draft } | { status: 'fuzzy'; candidates: Draft[] } | null

/** Busca la comida en el historial que ya está en el móvil. Funciona sin conexión. */
export function matchLocally(text: string, dishes: Dish[]): LocalMatch {
  const norm = normalize(text)
  if (!norm) return null
  const exact = dishes.find((d) => d.norm === norm || d.aliases.includes(norm))
  if (exact) return { status: 'exact', draft: draftFromDish(exact, 'exact', text) }

  const candidates: [Dish, string][] = []
  for (const dish of dishes) {
    candidates.push([dish, dish.norm])
    for (const alias of dish.aliases) candidates.push([dish, alias])
  }
  const best = new Map<number, [Dish, number]>()
  for (const [dish, score] of findSimilar(norm, candidates, undefined, 6)) {
    if ((best.get(dish.id)?.[1] ?? 0) < score) best.set(dish.id, [dish, score])
  }
  const ranked = [...best.values()].sort((a, b) => b[1] - a[1]).slice(0, 3)
  if (!ranked.length) return null
  return { status: 'fuzzy', candidates: ranked.map(([dish, score]) => draftFromDish(dish, 'fuzzy', text, score)) }
}

/** Sugerencias mientras se escribe: comidas del historial que contienen lo tecleado. */
export function suggestDishes(text: string, dishes: Dish[], limit = 4): Dish[] {
  const norm = normalize(text)
  if (norm.length < 2) return []
  const words = norm.split(' ')
  return dishes
    .filter((d) => words.every((w) => d.norm.includes(w) || normalize(d.name).includes(w)))
    .sort((a, b) => Number(b.favorite) - Number(a.favorite) || b.use_count - a.use_count)
    .slice(0, limit)
}

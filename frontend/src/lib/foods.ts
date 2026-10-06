import { round1 } from './products'
import { normalize } from './textnorm'
import type { FoodEntry, Item, Product } from './types'

export interface Per100 {
  kcal100: number
  protein100: number
  carbs100: number
  fat100: number
}

/** Sugerencia al escribir el nombre de un ingrediente: de la caché o de un producto con etiqueta. */
export interface FoodSuggestion extends Per100 {
  key: string
  name: string
  productId: number | null
  /** Gramos de una unidad, si se conoce (para proponer una cantidad razonable). */
  unitGrams: number | null
}

/** Ingredientes conocidos que contienen todas las palabras escritas. Los productos con etiqueta van primero. */
export function searchFoods(query: string, foods: FoodEntry[], products: Product[], limit = 5): FoodSuggestion[] {
  const words = normalize(query).split(' ').filter(Boolean)
  if (!words.length || words.join('').length < 2) return []
  const matches = (text: string) => {
    const norm = normalize(text)
    return words.every((w) => norm.includes(w))
  }
  const fromProducts: FoodSuggestion[] = products
    .filter((p) => matches(`${p.name} ${p.alias}`))
    .map((p) => ({
      key: `p${p.id}`,
      name: p.alias || p.name,
      productId: p.id,
      unitGrams: p.unit_grams,
      kcal100: p.kcal100,
      protein100: p.protein100,
      carbs100: p.carbs100,
      fat100: p.fat100,
    }))
  const seen = new Set(fromProducts.map((p) => normalize(p.name)))
  const fromFoods: FoodSuggestion[] = []
  for (const food of foods) {
    if (!matches(food.name) && !matches(food.norm)) continue
    const key = normalize(food.name)
    if (seen.has(key)) continue
    seen.add(key)
    const unit = Object.entries(food.unit_grams ?? {}).find(([name]) => name !== 'ml')
    fromFoods.push({
      key: `f${food.norm}`,
      name: food.name,
      productId: null,
      unitGrams: unit ? unit[1] : null,
      kcal100: food.kcal100,
      protein100: food.protein100,
      carbs100: food.carbs100,
      fat100: food.fat100,
    })
  }
  return [...fromProducts, ...fromFoods].slice(0, limit)
}

export interface ManualInput {
  name: string
  grams: number
  /** Los valores escritos son por 100 g o del total de esos gramos. */
  basis: 'per100' | 'total'
  kcal: number | null
  protein: number
  carbs: number
  fat: number
  productId?: number | null
}

/** Las calorías que salen de los macros (4/4/9). */
export const kcalFromMacros = (protein: number, carbs: number, fat: number) => protein * 4 + carbs * 4 + fat * 9

/** Qué no cuadra en lo escrito, o null si se puede añadir. */
export function manualProblem(input: ManualInput): string | null {
  if (!input.name.trim()) return 'Ponle nombre al ingrediente.'
  if (!(input.grams > 0) || input.grams > 5000) return 'Indica los gramos (entre 1 y 5.000).'
  const values = [input.kcal ?? 0, input.protein, input.carbs, input.fat]
  if (values.some((v) => !Number.isFinite(v) || v < 0)) return 'Las cifras no pueden ser negativas.'
  const factor = input.basis === 'per100' ? 1 : 100 / input.grams
  if ((input.protein + input.carbs + input.fat) * factor > 105) {
    return input.basis === 'per100'
      ? 'Proteínas, hidratos y grasas no pueden sumar más de 100 g por cada 100 g.'
      : 'Esos macros no caben en esos gramos: revisa las cifras o cambia a «por 100 g».'
  }
  if ((input.kcal ?? 0) * factor > 950) return 'Demasiadas calorías para ese peso: ¿son por 100 g o del total?'
  return null
}

/** Ingrediente listo para la comida, con sus totales. Sin calorías escritas, salen de los macros. */
export function manualItem(input: ManualInput): Item {
  const factor = input.basis === 'per100' ? input.grams / 100 : 1
  const kcal = input.kcal ?? kcalFromMacros(input.protein, input.carbs, input.fat)
  return {
    name: input.name.trim().toLowerCase(),
    qty: input.grams,
    unit: 'g',
    grams: input.grams,
    kcal: round1(kcal * factor),
    protein: round1(input.protein * factor),
    carbs: round1(input.carbs * factor),
    fat: round1(input.fat * factor),
    product_id: input.productId ?? null,
    manual: !input.productId,
  }
}

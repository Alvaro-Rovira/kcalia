import { round1 } from './products'
import type { Item } from './types'

/** Densidad del etanol: los grados (% vol) son mililitros de alcohol por cada 100 ml. */
const ETHANOL_G_PER_ML = 0.789
export const KCAL_PER_G_ALCOHOL = 7

export interface Drink {
  key: string
  name: string
  ml: number
  /** Graduación, % vol. */
  abv: number
  /** Hidratos por 100 ml (azúcares de la cerveza, el vermut o el refresco del cubata). */
  carbs100: number
  protein100?: number
}

export const DRINKS: Drink[] = [
  { key: 'cana', name: 'Caña de cerveza', ml: 200, abv: 5, carbs100: 3.6, protein100: 0.4 },
  { key: 'tercio', name: 'Tercio de cerveza', ml: 330, abv: 5, carbs100: 3.6, protein100: 0.4 },
  { key: 'tinto', name: 'Copa de vino tinto', ml: 150, abv: 13.5, carbs100: 2.6 },
  { key: 'blanco', name: 'Copa de vino blanco', ml: 150, abv: 12, carbs100: 2.6 },
  { key: 'cava', name: 'Copa de cava', ml: 100, abv: 11.5, carbs100: 1.5 },
  { key: 'sidra', name: 'Vaso de sidra', ml: 200, abv: 5, carbs100: 3 },
  { key: 'vermut', name: 'Vermut', ml: 100, abv: 15, carbs100: 13 },
  { key: 'chupito', name: 'Chupito', ml: 40, abv: 40, carbs100: 0 },
  // 50 ml de destilado (40 %) con 200 ml de refresco de cola: 250 ml al 8 %, 8,5 g de hidratos por 100 ml.
  { key: 'cubata', name: 'Cubata', ml: 250, abv: 8, carbs100: 8.5 },
]

export function alcoholGrams(ml: number, abv: number): number {
  return (ml * abv * ETHANOL_G_PER_ML) / 100
}

/** El ingrediente de una bebida: el alcohol cuenta 7 kcal por gramo, más sus hidratos y proteínas. */
export function drinkItem(drink: Pick<Drink, 'name' | 'ml' | 'abv' | 'carbs100' | 'protein100'>): Item {
  const alcohol = alcoholGrams(drink.ml, drink.abv)
  const carbs = (drink.carbs100 * drink.ml) / 100
  const protein = ((drink.protein100 ?? 0) * drink.ml) / 100
  return {
    name: drink.name.toLowerCase(),
    qty: drink.ml,
    unit: 'ml',
    grams: drink.ml,
    kcal: round1(alcohol * KCAL_PER_G_ALCOHOL + carbs * 4 + protein * 4),
    protein: round1(protein),
    carbs: round1(carbs),
    fat: 0,
    alcohol: round1(alcohol),
  }
}

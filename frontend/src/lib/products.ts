/**
 * Espejo de backend/app/products.py: empareja lo que escribes con una etiqueta guardada y multiplica.
 * Se prueba contra el mismo fichero de casos que el servidor (backend/tests/fixtures/product_cases.json).
 */
import { foodKey, isNumber, normalize, parsePart, ratio, singular, splitParts, UNITS } from './textnorm'
import type { Draft, Item, Product } from './types'

const TOKEN_SIMILARITY = 0.85
const GENERIC_UNITS = new Set<string | null>([null, 'pieza', 'racion'])
const STOPWORDS = new Set(['con'])
const UNIT_WORDS = new Set<string>([...UNITS.keys(), ...UNITS.values()])
const MASS: Record<string, number> = { g: 1, kg: 1000 }
const VOLUME: Record<string, number> = { ml: 1, cl: 10, l: 1000 }

export type ProductMatchInfo = Pick<
  Product,
  'id' | 'name' | 'alias' | 'basis' | 'kcal100' | 'protein100' | 'carbs100' | 'fat100' | 'unit_label' | 'unit_grams'
>

/** Redondeo a un decimal igual que el del servidor (mitades hacia arriba). */
export const round1 = (value: number): number => Math.floor(value * 10 + 0.5) / 10

export function tokens(text: string): Set<string> {
  const out = new Set<string>()
  for (const t of normalize(text).split(' ')) {
    if (t && !isNumber(t) && !UNIT_WORDS.has(t) && !STOPWORDS.has(t)) out.add(singular(t))
  }
  return out
}

const same = (a: string, b: string) => a === b || ratio(a, b) >= TOKEN_SIMILARITY
const covered = (wanted: Set<string>, pool: Set<string>) => [...wanted].every((w) => [...pool].some((p) => same(w, p)))
const equal = (a: Set<string>, b: Set<string>) => a.size > 0 && b.size > 0 && covered(a, b) && covered(b, a)
const union = (a: Set<string>, b: Set<string>) => new Set([...a, ...b])
const minus = (a: Set<string>, b: Set<string>) => new Set([...a].filter((x) => !b.has(x)))

export function matchProduct(wanted: Set<string>, products: ProductMatchInfo[]): ProductMatchInfo | null {
  if (!wanted.size) return null
  let best: ProductMatchInfo | null = null
  let bestKey: [number, number] = [-1, -1]
  for (const product of products) {
    const name = tokens(product.name)
    const aliasTokens = tokens(product.alias)
    const alias = aliasTokens.size ? aliasTokens : name
    if (!union(alias, name).size) continue
    const pool = union(alias, name)
    const label = product.unit_label ? tokens(product.unit_label) : new Set<string>()
    const withoutUnit = minus(wanted, label)
    const candidates = [wanted]
    if (withoutUnit.size && withoutUnit.size !== wanted.size) candidates.push(withoutUnit)
    for (const words of candidates) {
      const exact = equal(words, alias) || equal(words, name)
      if (!exact && !(covered(alias, words) && covered(words, pool))) continue
      const key: [number, number] = [exact ? 1 : 0, alias.size]
      if (key[0] > bestKey[0] || (key[0] === bestKey[0] && key[1] > bestKey[1])) {
        best = product
        bestKey = key
      }
      break
    }
  }
  return best
}

export function itemFor(product: ProductMatchInfo, qty: number, unit: string | null): Item | null {
  if (qty <= 0) return null
  let grams: number
  if (unit && unit in MASS) grams = qty * MASS[unit]
  else if (unit && unit in VOLUME) grams = qty * VOLUME[unit]
  else {
    const own = product.unit_label ? (UNITS.get(foodKey(product.unit_label)) ?? null) : null
    if (!(product.unit_grams && (GENERIC_UNITS.has(unit) || unit === own))) return null
    grams = qty * product.unit_grams
  }
  if (grams <= 0 || grams > 5000) return null
  const factor = grams / 100
  return {
    name: product.name,
    qty,
    unit: unit ?? 'pieza',
    grams: round1(grams),
    kcal: round1(product.kcal100 * factor),
    protein: round1(product.protein100 * factor),
    carbs: round1(product.carbs100 * factor),
    fat: round1(product.fat100 * factor),
    product_id: product.id,
  }
}

function tryPiece(piece: string, products: ProductMatchInfo[]): Item | null {
  const [qty, unit, name] = parsePart(piece)
  const product = name ? matchProduct(tokens(name), products) : null
  return product ? itemFor(product, qty, unit) : null
}

export interface Resolution {
  /** Ingredientes que salen de productos guardados. */
  items: Item[]
  /** Lo que no es de ningún producto: sigue su camino (caché, IA). */
  rest: string[]
}

/** «dos yogures ligeros con una manzana» -> 2 × yogur ligero (de la etiqueta) y «una manzana» para lo demás. */
export function resolveText(text: string, products: ProductMatchInfo[]): Resolution {
  const items: Item[] = []
  const rest: string[] = []
  if (!products.length) return { items, rest: text.trim() ? [text.trim()] : [] }
  for (const fragment of splitParts(text)) {
    const whole = tryPiece(fragment, products)
    if (whole) {
      items.push(whole)
      continue
    }
    const pieces = fragment
      .split(/\s+con\s+/i)
      .map((p) => p.trim())
      .filter(Boolean)
    const found = pieces.length > 1 ? pieces.map((p) => tryPiece(p, products)) : [null]
    if (!found.some(Boolean)) {
      rest.push(fragment)
      continue
    }
    let pending: string[] = []
    pieces.forEach((piece, i) => {
      const item = found[i]
      if (item) {
        items.push(item)
        if (pending.length) rest.push(pending.join(' con '))
        pending = []
      } else pending.push(piece)
    })
    if (pending.length) rest.push(pending.join(' con '))
  }
  return { items, rest }
}

const sumOf = (items: Item[], key: 'kcal' | 'protein' | 'carbs' | 'fat') => round1(items.reduce((n, i) => n + i[key], 0))

/** Borrador de una comida hecha solo con productos guardados (igual que el que arma el servidor). */
export function draftFromProducts(text: string, items: Item[]): Draft {
  const names = [...new Set(items.map((i) => i.name))]
  const joined = (names.length <= 2 ? names.join(' y ') : names.join(', ')).slice(0, 60)
  return {
    name: joined.charAt(0).toUpperCase() + joined.slice(1),
    text,
    items,
    kcal: sumOf(items, 'kcal'),
    protein: sumOf(items, 'protein'),
    carbs: sumOf(items, 'carbs'),
    fat: sumOf(items, 'fat'),
    confidence: 0.9,
    assumptions: [`Calculado con la etiqueta que guardaste de: ${names.join(', ')}`, 'Sin consultar a la IA'],
    source: 'product',
    dish_id: null,
  }
}

/** Una unidad del producto (o 100 g si no se sabe lo que pesa una unidad), para añadirlo de un toque. */
export function singleItem(product: ProductMatchInfo): Item {
  const unitItem = product.unit_grams ? itemFor(product, 1, null) : null
  return unitItem ?? (itemFor(product, 100, 'g') as Item)
}

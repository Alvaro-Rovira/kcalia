/**
 * Sugerencia para cerrar el día: qué comer para acercarse a las calorías que quedan SIN PASARSE, priorizando la
 * proteína que falta. Función pura, sin IA y sin red: funciona en el móvil con lo que ya hay guardado.
 *
 * Restricción dura: las calorías de una sugerencia, tal como se guardarían (itemsTotal), nunca superan las que quedan.
 */
import { itemsTotal } from './macros'
import { round1, singleItem } from './products'
import { normalize } from './textnorm'
import type { Dish, FoodEntry, Item, Macros, Product, Slot } from './types'

export interface Remaining extends Macros {}

export type CandidateKind = 'dish' | 'product' | 'food' | 'generic'

/** Algo que se puede sugerir, en su ración base (×1). */
export interface Candidate {
  key: string
  kind: CandidateKind
  name: string
  items: Item[]
  useCount: number
  slotCounts?: Partial<Record<Slot, number>>
  dishId?: number | null
  /** Si la ración se puede ajustar a gramos libres (ingredientes y productos por 100 g). */
  byGrams?: boolean
}

export interface SuggestionPart {
  key: string
  name: string
  factor: number
  grams: number
  /** Ración en gramos libres (ingredientes y productos por 100 g): se enseña en gramos. */
  byGrams: boolean
}

export interface Suggestion extends Macros {
  key: string
  name: string
  parts: SuggestionPart[]
  items: Item[]
  dishId: number | null
  /** Parte de la proteína que falta que cubriría (0 a 1). */
  proteinCovered: number
  score: number
  generic: boolean
}

export interface SuggestInput {
  remaining: Remaining
  /** Hora local (0-23). */
  hour: number
  candidates: Candidate[]
  /** Ocultados para siempre («No sugerir más esto»). */
  hidden?: Set<string>
  /** Sugeridos ayer o descartados hoy: bajan para dar variedad. */
  recent?: Set<string>
  limit?: number
}

const FACTORS = [0.5, 1, 1.5, 2]
/** Ración máxima al ajustar por gramos: nadie cena 400 g de pechuga para cuadrar números. */
const MAX_GRAMS = 250
const MAX_PAIR_POOL = 14
const MIN_KCAL_PART = 25

/** Genéricos razonables para cuando no hay nada guardado que encaje (valores BEDCA aproximados). */
export const GENERIC: Candidate[] = [
  generic('yogur natural', 'Yogur natural', 'pieza', 1, 125, 61, 3.5, 4.7, 3.3),
  generic('queso fresco batido', 'Queso fresco batido 0 %', 'g', 250, 250, 46, 8, 3.5, 0.2),
  generic('atun al natural', 'Lata de atún al natural', 'lata', 1, 56, 110, 25, 0, 1),
  generic('huevo cocido', 'Huevo cocido', 'pieza', 1, 55, 143, 12.6, 0.7, 9.5),
  generic('pavo en lonchas', 'Pavo en lonchas', 'loncha', 3, 60, 105, 20, 1.5, 2),
  generic('manzana', 'Una manzana', 'pieza', 1, 150, 52, 0.3, 14, 0.2),
  generic('leche semidesnatada', 'Vaso de leche semidesnatada', 'ml', 200, 200, 46, 3.3, 4.8, 1.6),
  generic('nueces', 'Puñado de nueces', 'g', 30, 30, 654, 15, 14, 65),
]

function generic(key: string, name: string, unit: string, qty: number, grams: number, kcal100: number, p100: number, c100: number, f100: number): Candidate {
  const factor = grams / 100
  return {
    key: `generic:${key}`,
    kind: 'generic',
    name,
    useCount: 0,
    byGrams: false,
    items: [
      {
        name: key.replace(/_/g, ' '),
        qty,
        unit,
        grams,
        kcal: round1(kcal100 * factor),
        protein: round1(p100 * factor),
        carbs: round1(c100 * factor),
        fat: round1(f100 * factor),
      },
    ],
  }
}

export function scaleItems(items: Item[], factor: number): Item[] {
  return items.map((item) => ({
    ...item,
    qty: Math.round(item.qty * factor * 100) / 100,
    grams: round1(item.grams * factor),
    kcal: round1(item.kcal * factor),
    protein: round1(item.protein * factor),
    carbs: round1(item.carbs * factor),
    fat: round1(item.fat * factor),
    ...(item.fiber != null ? { fiber: round1(item.fiber * factor) } : {}),
    manual: false,
  }))
}

const hasAlcohol = (c: Candidate) => c.items.some((i) => (i.alcohol ?? 0) > 0)
const gramsOf = (items: Item[]) => items.reduce((sum, i) => sum + (i.grams || 0), 0)

/** Raciones posibles de un candidato: ×0,5 a ×2 y, si va por gramos, la que más se acerca en pasos de 10 g. */
function portions(candidate: Candidate, maxKcal: number): number[] {
  const base = itemsTotal(candidate.items).kcal
  if (base <= 0) return []
  const factors = new Set(FACTORS)
  const grams = gramsOf(candidate.items)
  if (candidate.byGrams && grams > 0) {
    const fit = Math.floor(((maxKcal / base) * grams) / 10) * 10
    const clamped = Math.min(MAX_GRAMS, fit)
    if (clamped >= 30) factors.add(Math.round((clamped / grams) * 1000) / 1000)
  }
  // Por gramos, nunca más de MAX_GRAMS en total; por raciones, como mucho el doble.
  return [...factors].filter((f) => f > 0 && f <= 2 && (!candidate.byGrams || grams * f <= MAX_GRAMS + 0.01))
}

interface Option {
  parts: { candidate: Candidate; factor: number }[]
  items: Item[]
  totals: Macros
}

function option(parts: { candidate: Candidate; factor: number }[]): Option {
  const items = parts.flatMap(({ candidate, factor }) => scaleItems(candidate.items, factor))
  return { parts, items, totals: itemsTotal(items) }
}

function slotAffinity(candidate: Candidate, hour: number): number {
  const counts = candidate.slotCounts ?? {}
  const total = Object.values(counts).reduce((s, n) => s + (n ?? 0), 0)
  if (!total) return 0
  const late = (counts.cena ?? 0) + (counts.snack ?? 0) + (counts.merienda ?? 0)
  const breakfast = counts.desayuno ?? 0
  // Por la noche suben las cosas de cena, merienda o picoteo; un desayuno típico baja un poco.
  return (late / total) * 6 - (hour >= 19 ? (breakfast / total) * 3 : 0)
}

/** De madrugada (de 23 a 5) la sugerencia apunta a algo ligero, quede lo que quede. */
const LATE_CAP = 350
const isLate = (hour: number) => hour >= 23 || hour < 5

function score(opt: Option, input: SuggestInput): number {
  const { remaining, hour } = input
  const { totals } = opt
  const late = isLate(hour)
  const goal = late ? Math.min(remaining.kcal, LATE_CAP) : remaining.kcal
  // 1) Cercanía a las calorías que quedan: lo que más pesa.
  let value = (Math.min(totals.kcal, goal) / goal) * 60
  // 2) Proteína: cuanto más cubra de la que falta, mejor (y si ya está cubierta, cuenta poco).
  if (remaining.protein > 1) value += (Math.min(totals.protein, remaining.protein) / remaining.protein) * 25
  else value += Math.min(totals.protein, 30) * 0.1
  // 3) No pasarse de grasas ni de hidratos.
  value -= Math.max(0, totals.fat - Math.max(0, remaining.fat)) * 1.2
  value -= Math.max(0, totals.carbs - Math.max(0, remaining.carbs)) * 0.4
  // 4) Momento del día: nada copioso de madrugada.
  if (late && totals.kcal > LATE_CAP) value -= 40
  for (const { candidate } of opt.parts) value += slotAffinity(candidate, hour)
  // 5) Lo que de verdad come: frecuencia de uso (media de las partes).
  for (const { candidate, factor } of opt.parts) {
    value += Math.min(8, Math.log2(1 + candidate.useCount) * 2.5) / opt.parts.length
    if (candidate.kind === 'generic') value -= 6
    if (factor === 2) value -= 3
    else if (factor === 1.5) value -= 1
    else if (factor !== 1 && factor !== 0.5) value -= 0.5
  }
  // 6) Variedad: lo sugerido ayer o descartado hoy, más abajo.
  if (opt.parts.some(({ candidate }) => input.recent?.has(candidate.key))) value -= 15
  if (opt.parts.length > 1) value -= 1
  return value
}

function label(parts: { candidate: Candidate; factor: number }[]): string {
  return parts.map(({ candidate }) => candidate.name).join(' + ')
}

/**
 * Las mejores sugerencias para lo que queda del día, de mejor a peor, sin repetir lo mismo con otra ración.
 * Si no hay nada propio que encaje, completa con genéricos sencillos.
 */
export function suggest(input: SuggestInput): Suggestion[] {
  const limit = input.limit ?? 3
  if (!(input.remaining.kcal > 0)) return []
  const own = rank(input, input.candidates.filter((c) => c.kind !== 'generic'))
  if (own.length >= limit) return own.slice(0, limit)
  const generic = rank(input, GENERIC).filter((g) => !own.some((o) => o.key === g.key))
  return [...own, ...generic].slice(0, limit)
}

function rank(input: SuggestInput, candidates: Candidate[]): Suggestion[] {
  const { remaining } = input
  const usable = candidates.filter((c) => !hasAlcohol(c) && !input.hidden?.has(c.key) && itemsTotal(c.items).kcal > 0)

  const best = new Map<string, { opt: Option; score: number }>()
  const consider = (opt: Option) => {
    // Restricción dura: lo que se guardaría no puede pasarse ni una décima.
    if (opt.totals.kcal > remaining.kcal || opt.totals.kcal <= 0) return
    const key = opt.parts
      .map(({ candidate }) => candidate.key)
      .sort()
      .join('+')
    const s = score(opt, input)
    const current = best.get(key)
    if (!current || s > current.score) best.set(key, { opt, score: s })
  }

  for (const candidate of usable) {
    for (const factor of portions(candidate, remaining.kcal)) consider(option([{ candidate, factor }]))
  }

  // Parejas (yogur + fruta…): entre los más usados, con raciones que dejen sitio a las dos.
  const pool = [...usable]
    .filter((c) => itemsTotal(c.items).kcal * 0.5 < remaining.kcal)
    .sort((a, b) => b.useCount - a.useCount)
    .slice(0, MAX_PAIR_POOL)
  for (let i = 0; i < pool.length; i++) {
    for (let j = i + 1; j < pool.length; j++) {
      for (const fa of [0.5, 1, 1.5]) {
        for (const fb of [0.5, 1, 1.5]) {
          const opt = option([
            { candidate: pool[i], factor: fa },
            { candidate: pool[j], factor: fb },
          ])
          const small = opt.parts.some(({ candidate, factor }) => itemsTotal(candidate.items).kcal * factor < MIN_KCAL_PART)
          if (!small) consider(opt)
        }
      }
    }
  }

  const out: Suggestion[] = []
  const used = new Set<string>()
  for (const { opt, score: s } of [...best.values()].sort((a, b) => b.score - a.score)) {
    // Cada candidato aparece una sola vez en la lista (solo o en pareja), para que las opciones sean distintas.
    if (opt.parts.some(({ candidate }) => used.has(candidate.key))) continue
    opt.parts.forEach(({ candidate }) => used.add(candidate.key))
    out.push(toSuggestion(opt, s, remaining))
  }
  return out
}

function toSuggestion(opt: Option, score: number, remaining: Remaining): Suggestion {
  const generic = opt.parts.every(({ candidate }) => candidate.kind === 'generic')
  const dish = opt.parts.length === 1 && opt.parts[0].candidate.kind === 'dish' ? (opt.parts[0].candidate.dishId ?? null) : null
  return {
    key: opt.parts.map(({ candidate }) => candidate.key).join('+'),
    name: label(opt.parts),
    parts: opt.parts.map(({ candidate, factor }) => ({
      key: candidate.key,
      name: candidate.name,
      factor,
      grams: round1(gramsOf(candidate.items) * factor),
      byGrams: !!candidate.byGrams,
    })),
    items: opt.items,
    dishId: dish,
    ...opt.totals,
    proteinCovered: remaining.protein > 0 ? Math.min(1, opt.totals.protein / remaining.protein) : 1,
    score,
    generic,
  }
}

/** «200 g» si va por gramos; si no, «1 ración», «media ración», «1,5 raciones». */
export function portionLabel(part: SuggestionPart): string {
  if (part.byGrams) return `${Math.round(part.grams)} g`
  if (part.factor === 0.5) return 'media ración'
  if (part.factor === 1) return '1 ración'
  return `${String(part.factor).replace('.', ',')} raciones`
}

const CONDIMENT = /\b(aceite|mantequilla|margarina|azucar|sal|vinagre|ketchup|mayonesa|cafe|te|infusion|edulcorante)\b/

/** Candidatos a partir de lo guardado: comidas conocidas, productos con etiqueta y la caché de ingredientes. */
export function buildCandidates(data: { dishes: Dish[]; products: Product[]; foods?: FoodEntry[] }): Candidate[] {
  const out: Candidate[] = []
  for (const dish of data.dishes) {
    out.push({ key: `dish:${dish.id}`, kind: 'dish', name: dish.name, items: dish.items, useCount: dish.use_count, slotCounts: dish.slot_counts, dishId: dish.id })
  }
  for (const product of data.products) {
    out.push({
      key: `product:${product.id}`,
      kind: 'product',
      name: product.alias ? product.alias[0].toUpperCase() + product.alias.slice(1) : product.name,
      items: [singleItem(product)],
      useCount: product.use_count,
      slotCounts: product.slot_counts,
      byGrams: !product.unit_grams,
    })
  }
  for (const food of data.foods ?? []) {
    const plain = normalize(food.name)
    if (food.kcal100 > 700 || food.fat100 > 60 || (food.alcohol100 ?? 0) > 0 || CONDIMENT.test(plain)) continue
    const unit = Object.entries(food.unit_grams ?? {}).find(([name]) => name !== 'ml')
    const grams = unit ? unit[1] : 100
    const factor = grams / 100
    out.push({
      key: `food:${food.norm}`,
      kind: 'food',
      name: food.name[0].toUpperCase() + food.name.slice(1),
      useCount: 0,
      byGrams: true,
      items: [
        {
          name: food.name,
          qty: unit ? 1 : grams,
          unit: unit ? unit[0] : 'g',
          grams,
          kcal: round1(food.kcal100 * factor),
          protein: round1(food.protein100 * factor),
          carbs: round1(food.carbs100 * factor),
          fat: round1(food.fat100 * factor),
          ...(food.fiber100 != null ? { fiber: round1(food.fiber100 * factor) } : {}),
        },
      ],
    })
  }
  return out
}

import { describe, expect, it } from 'vitest'
import { itemsTotal } from './macros'
import { buildCandidates, GENERIC, portionLabel, suggest, type Candidate } from './suggest'
import type { Dish, FoodEntry, Item, Product } from './types'

const item = (name: string, kcal: number, protein: number, carbs: number, fat: number, grams = 100, extra: Partial<Item> = {}): Item => ({
  name, qty: 1, unit: 'pieza', grams, kcal, protein, carbs, fat, ...extra,
})
const cand = (key: string, items: Item[], over: Partial<Candidate> = {}): Candidate => ({ key, kind: 'dish', name: key, items, useCount: 5, ...over })

const yogur = cand('yogur', [item('yogur proteico', 80, 12, 5, 0.5, 150)], { useCount: 20 })
const fruta = cand('fruta', [item('manzana', 78, 0.4, 21, 0.3, 150)], { useCount: 15 })
const atun = cand('atun', [item('atún', 62, 14, 0, 0.6, 56)], { useCount: 8 })
const pizza = cand('pizza', [item('pizza', 750, 30, 90, 28, 300)], { useCount: 3 })
const cerveza = cand('cerveza', [item('cerveza', 87, 0.8, 7.2, 0, 200, { alcohol: 7.9 })], { useCount: 30 })

const R = (kcal: number, protein = 30, carbs = 40, fat = 15) => ({ kcal, protein, carbs, fat })

describe('sugerencia para cerrar el día', () => {
  it('nunca supera las calorías que quedan', () => {
    for (const s of suggest({ remaining: R(170), hour: 21, candidates: [yogur, fruta, atun, pizza] })) {
      expect(s.kcal).toBeLessThanOrEqual(170)
    }
  })

  it('prefiere acercarse a lo que queda y cubrir proteína', () => {
    const [first] = suggest({ remaining: R(165, 25), hour: 21, candidates: [yogur, fruta, atun] })
    expect(first.kcal).toBeGreaterThan(120)
    expect(first.protein).toBeGreaterThanOrEqual(12)
  })

  it('combina dos cosas (yogur + fruta) si encaja mejor', () => {
    const list = suggest({ remaining: R(160, 5), hour: 18, candidates: [yogur, fruta], limit: 3 })
    expect(list.some((s) => s.parts.length === 2)).toBe(true)
  })

  it('ajusta la ración: media pizza no, pizza entera tampoco si no cabe', () => {
    const list = suggest({ remaining: R(400, 10, 80, 30), hour: 14, candidates: [pizza] })
    expect(list.every((s) => s.kcal <= 400)).toBe(true)
    expect(list.find((s) => s.key === 'pizza')?.parts[0].factor).toBe(0.5)
  })

  it('nada con alcohol', () => {
    const list = suggest({ remaining: R(300), hour: 22, candidates: [cerveza, yogur] })
    expect(list.some((s) => s.key.includes('cerveza'))).toBe(false)
  })

  it('respeta lo ocultado y baja lo sugerido ayer', () => {
    const hidden = suggest({ remaining: R(170), hour: 21, candidates: [yogur, fruta, atun], hidden: new Set(['yogur']) })
    expect(hidden.some((s) => s.parts.some((p) => p.key === 'yogur'))).toBe(false)
    const normal = suggest({ remaining: R(80, 12), hour: 21, candidates: [yogur, atun], limit: 1 })[0].key
    const varied = suggest({ remaining: R(80, 12), hour: 21, candidates: [yogur, atun], limit: 1, recent: new Set([normal]) })[0].key
    expect(varied).not.toBe(normal)
  })

  it('de madrugada evita lo copioso', () => {
    const cena = cand('cena', [item('plato', 600, 40, 60, 20, 400)], { useCount: 50 })
    const ligera = cand('ligera', [item('yogur', 130, 15, 8, 3, 170)], { useCount: 2 })
    const list = suggest({ remaining: R(650, 40, 70, 25), hour: 0, candidates: [cena, ligera] })
    // A las 12 de la noche, ni el plato entero (600 kcal) aunque quepa: como mucho algo de unas 350.
    expect(list[0].kcal).toBeLessThanOrEqual(350)
    const dinner = suggest({ remaining: R(650, 40, 70, 25), hour: 21, candidates: [cena, ligera] })
    expect(dinner[0].kcal).toBeGreaterThan(350) // a las 9 sí cabe la cena entera
  })

  it('casos límite: 0, negativo, historial vacío y un solo favorito', () => {
    expect(suggest({ remaining: R(0), hour: 21, candidates: [yogur] })).toEqual([])
    expect(suggest({ remaining: R(-200), hour: 21, candidates: [yogur] })).toEqual([])
    const empty = suggest({ remaining: R(150), hour: 21, candidates: [] })
    expect(empty.length).toBeGreaterThan(0)
    expect(empty.every((s) => s.generic && s.kcal <= 150)).toBe(true)
    const one = suggest({ remaining: R(150), hour: 21, candidates: [yogur] })
    expect(one[0].key).toBe('yogur')
    expect(one.slice(1).every((s) => s.generic)).toBe(true)
  })

  it('las calorías de la sugerencia son las que se guardarían', () => {
    for (const s of suggest({ remaining: R(333.3), hour: 20, candidates: [yogur, fruta, atun, pizza] })) {
      expect(itemsTotal(s.items).kcal).toBe(s.kcal)
    }
  })
})

describe('propiedad: jamás se pasa de lo que queda (muchos casos aleatorios)', () => {
  // Generador determinista (mulberry32): mismo resultado en cada ejecución.
  function rng(seed: number) {
    return () => {
      seed |= 0
      seed = (seed + 0x6d2b79f5) | 0
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296
    }
  }
  it('2.000 escenarios con candidatos y restos aleatorios', () => {
    const random = rng(42)
    for (let n = 0; n < 2000; n++) {
      const candidates: Candidate[] = Array.from({ length: Math.floor(random() * 12) }, (_, i) => {
        const grams = 20 + random() * 400
        const kcal = Math.round(random() * 900 * 10) / 10
        const alcohol = random() < 0.1 ? random() * 15 : 0
        return cand(`c${i}`, [item(`x${i}`, kcal, random() * 60, random() * 100, random() * 40, grams, alcohol ? { alcohol } : {})], {
          useCount: Math.floor(random() * 40),
          byGrams: random() < 0.5,
          kind: (['dish', 'product', 'food'] as const)[Math.floor(random() * 3)],
        })
      })
      const remaining = R(Math.round((random() * 1600 - 200) * 10) / 10, random() * 120 - 20, random() * 200 - 30, random() * 80 - 20)
      const hidden = new Set(candidates.filter(() => random() < 0.1).map((c) => c.key))
      const list = suggest({ remaining, hour: Math.floor(random() * 24), candidates, hidden, limit: 3 })
      for (const s of list) {
        expect(s.kcal).toBeLessThanOrEqual(remaining.kcal)
        expect(itemsTotal(s.items).kcal).toBeLessThanOrEqual(remaining.kcal)
        expect(s.items.some((i) => (i.alcohol ?? 0) > 0)).toBe(false)
        expect(s.parts.some((p) => hidden.has(p.key))).toBe(false)
      }
      if (remaining.kcal <= 0) expect(list).toEqual([])
      expect(list.length).toBeLessThanOrEqual(3)
    }
  })
})

describe('candidatos a partir de lo guardado', () => {
  it('usa comidas, productos e ingredientes, sin aceites ni condimentos', () => {
    const dish = { id: 3, name: 'Tortilla', items: [item('huevo', 157, 14, 1, 10, 110)], use_count: 4, slot_counts: { cena: 4 } } as unknown as Dish
    const product = { id: 7, name: 'Yogur', alias: 'yogur ligero', basis: 'g', kcal100: 44, protein100: 4.1, carbs100: 6.5, fat100: 0.1, fiber100: null, unit_label: 'yogur', unit_grams: 125, use_count: 2 } as unknown as Product
    const foods: FoodEntry[] = [
      { name: 'aceite de oliva', norm: 'aceite oliva', kcal100: 884, protein100: 0, carbs100: 0, fat100: 100, unit_grams: {} },
      { name: 'sal', norm: 'sal', kcal100: 0, protein100: 0, carbs100: 0, fat100: 0, unit_grams: {} },
      { name: 'pan integral', norm: 'pan integral', kcal100: 250, protein100: 10, carbs100: 42, fat100: 3.5, fiber100: 7, unit_grams: { rebanada: 30 } },
    ]
    const list = buildCandidates({ dishes: [dish], products: [product], foods })
    expect(list.map((c) => c.key)).toEqual(['dish:3', 'product:7', 'food:pan integral'])
    expect(list[1].items[0]).toMatchObject({ grams: 125, kcal: 55, product_id: 7 })
    expect(list[2].items[0]).toMatchObject({ grams: 30, kcal: 75, fiber: 2.1, unit: 'rebanada' })
  })
  it('los genéricos no llevan alcohol y son razonables', () => {
    for (const g of GENERIC) expect(itemsTotal(g.items).kcal).toBeGreaterThan(40)
  })
})

describe('raciones razonables', () => {
  it('por gramos nunca más de 250 g y se enseña en gramos', () => {
    const pollo = cand('pollo', [item('pechuga', 165, 31, 0, 3.6, 100)], { byGrams: true, kind: 'food', useCount: 10 })
    const list = suggest({ remaining: R(1400, 120), hour: 20, candidates: [pollo] })
    const own = list.find((s) => s.key === 'pollo')!
    expect(own.parts[0].grams).toBeLessThanOrEqual(250)
    expect(portionLabel(own.parts[0])).toMatch(/^\d+ g$/)
  })
  it('por raciones, como mucho el doble y con nombre claro', () => {
    const list = suggest({ remaining: R(5000), hour: 20, candidates: [yogur] })
    expect(list.find((s) => s.key === 'yogur')!.parts[0].factor).toBeLessThanOrEqual(2)
    expect(portionLabel({ key: 'x', name: 'x', factor: 0.5, grams: 50, byGrams: false })).toBe('media ración')
    expect(portionLabel({ key: 'x', name: 'x', factor: 1.5, grams: 50, byGrams: false })).toBe('1,5 raciones')
  })
})

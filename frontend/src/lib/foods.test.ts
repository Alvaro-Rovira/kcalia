import { describe, expect, it } from 'vitest'
import { manualItem, manualProblem, searchFoods } from './foods'
import type { FoodEntry, Product } from './types'

const foods: FoodEntry[] = [
  { name: 'arroz blanco cocido', norm: 'arroz blanco cocido', kcal100: 130, protein100: 2.7, carbs100: 28, fat100: 0.3, unit_grams: {} },
  { name: 'huevo', norm: 'huevo', kcal100: 143, protein100: 12.6, carbs100: 0.7, fat100: 9.5, unit_grams: { pieza: 55 } },
  { name: 'aceite de oliva', norm: 'aceite oliva', kcal100: 884, protein100: 0, carbs100: 0, fat100: 100, unit_grams: { cda: 10 } },
]
const product = {
  id: 7, name: 'Yogur desnatado ligero', alias: 'yogur ligero', basis: 'g', kcal100: 44, protein100: 4.1, carbs100: 6.5, fat100: 0.1,
  fiber100: null, sugars100: null, salt100: null, unit_label: 'yogur', unit_grams: 125, has_image: false, use_count: 0,
  last_used_at: '', created_at: '',
} as Product

describe('searchFoods', () => {
  it('encuentra por palabras en cualquier orden y sin tildes', () => {
    expect(searchFoods('cocido arroz', foods, []).map((f) => f.name)).toEqual(['arroz blanco cocido'])
    expect(searchFoods('ACEITE', foods, [])[0].unitGrams).toBe(10)
  })
  it('pone primero los productos con etiqueta y no repite', () => {
    const found = searchFoods('yogur', foods, [product])
    expect(found[0]).toMatchObject({ productId: 7, name: 'yogur ligero', unitGrams: 125 })
  })
  it('no sugiere nada con menos de dos letras', () => {
    expect(searchFoods('a', foods, [])).toEqual([])
  })
})

describe('manualItem', () => {
  it('escala los valores por 100 g a los gramos indicados', () => {
    const item = manualItem({ name: 'Garbanzos', grams: 150, basis: 'per100', kcal: 164, protein: 8.9, carbs: 27, fat: 2.6 })
    expect(item).toMatchObject({ name: 'garbanzos', grams: 150, kcal: 246, protein: 13.4, carbs: 40.5, fat: 3.9, manual: true, unit: 'g' })
  })
  it('respeta los totales tal cual', () => {
    expect(manualItem({ name: 'tarta', grams: 90, basis: 'total', kcal: 320, protein: 4, carbs: 40, fat: 16 })).toMatchObject({ kcal: 320, fat: 16 })
  })
  it('sin calorías, las calcula con los macros', () => {
    expect(manualItem({ name: 'x', grams: 100, basis: 'per100', kcal: null, protein: 10, carbs: 10, fat: 10 }).kcal).toBe(170)
  })
  it('lo que viene de un producto no se aprende como ingrediente', () => {
    expect(manualItem({ name: 'yogur ligero', grams: 125, basis: 'per100', kcal: 44, protein: 4.1, carbs: 6.5, fat: 0.1, productId: 7 })).toMatchObject({
      product_id: 7,
      manual: false,
      kcal: 55,
    })
  })
})

describe('manualProblem', () => {
  const ok = { name: 'pan', grams: 40, basis: 'per100' as const, kcal: 265, protein: 9, carbs: 51, fat: 3 }
  it('acepta un ingrediente normal', () => expect(manualProblem(ok)).toBeNull())
  it('exige nombre y gramos', () => {
    expect(manualProblem({ ...ok, name: ' ' })).toMatch(/nombre/)
    expect(manualProblem({ ...ok, grams: 0 })).toMatch(/gramos/)
  })
  it('detecta macros imposibles por 100 g y en total', () => {
    expect(manualProblem({ ...ok, protein: 60, carbs: 60 })).toMatch(/100 g/)
    expect(manualProblem({ ...ok, basis: 'total', grams: 20, protein: 15, carbs: 10, fat: 0 })).toMatch(/no caben/)
  })
  it('avisa de calorías imposibles', () => expect(manualProblem({ ...ok, kcal: 2000 })).toMatch(/Demasiadas/))
})

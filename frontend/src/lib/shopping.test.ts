import { describe, expect, it } from 'vitest'
import { fmtGrams, shoppingList, type PlanEntry } from './shopping'

const item = (name: string, grams: number, qty = grams, unit = 'g') => ({ name, grams, qty, unit, kcal: 0, protein: 0, carbs: 0, fat: 0 })
const entry = (items: ReturnType<typeof item>[], servings = 1): PlanEntry => ({
  client_id: Math.random().toString(), date: '2026-10-06', slot: 'comida', name: 'x', items, servings, dish_id: null, source: 'dish', kcal: 0, protein: 0, carbs: 0, fat: 0,
})

describe('lista de la compra', () => {
  it('junta el mismo alimento aunque se escriba en plural y multiplica las raciones', () => {
    const list = shoppingList([entry([item('huevo', 110, 2, 'pieza')]), entry([item('huevos', 55, 1, 'pieza')], 2)])
    expect(list).toEqual([{ key: 'huevo', name: 'huevo', grams: 220, units: { qty: 4, unit: 'pieza' }, meals: 2 }])
  })
  it('si se mezclan unidades y gramos, solo cuenta el peso', () => {
    const list = shoppingList([entry([item('arroz', 200)]), entry([item('arroz', 80, 1, 'taza')])])
    expect(list[0]).toMatchObject({ grams: 280, units: null })
  })
  it('ordena alfabéticamente y formatea el peso', () => {
    expect(shoppingList([entry([item('tomate', 150), item('aceite de oliva', 10)])]).map((l) => l.name)).toEqual(['aceite de oliva', 'tomate'])
    expect(fmtGrams(250)).toBe('250 g')
    expect(fmtGrams(1250)).toBe('1,3 kg')
  })
})

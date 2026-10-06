import { describe, expect, it } from 'vitest'
import { copyInputs } from './copy'
import type { Meal } from './types'

const meal = (over: Partial<Meal>): Meal => ({
  id: 1, client_id: 'a', date: '2026-10-01', slot: 'comida', name: 'Lentejas', text: 'lentejas', servings: 1.5,
  items: [{ name: 'lentejas', qty: 1, unit: 'plato', grams: 330, kcal: 383, protein: 30, carbs: 66, fat: 1.3, manual: true }],
  kcal: 574.5, protein: 45, carbs: 99, fat: 2, source: 'ai', confidence: 0.8, assumptions: [], dish_id: 4, created_at: '', ...over,
})

describe('copyInputs', () => {
  it('copia una comida a otro día y momento con un client_id nuevo', () => {
    const [copy] = copyInputs([meal({})], { date: '2026-10-06', slot: 'cena' }, () => 'nuevo')
    expect(copy).toMatchObject({ client_id: 'nuevo', date: '2026-10-06', slot: 'cena', servings: 1.5, dish_id: 4, source: 'recent', via: 'tap' })
    // El ingrediente ya se aprendió con la comida original: la copia no lo vuelve a enseñar.
    expect(copy.items[0].manual).toBe(false)
  })
  it('al copiar un día, cada comida conserva su momento y su propio id', () => {
    let n = 0
    const copies = copyInputs([meal({ slot: 'desayuno' }), meal({ client_id: 'b', slot: 'cena' })], { date: '2026-10-06' }, () => `id-${++n}`)
    expect(copies.map((c) => [c.client_id, c.slot, c.date])).toEqual([
      ['id-1', 'desayuno', '2026-10-06'],
      ['id-2', 'cena', '2026-10-06'],
    ])
  })
  it('sin generador fijo, los ids no se repiten', () => {
    const ids = copyInputs([meal({}), meal({}), meal({})], { date: '2026-10-06' }).map((c) => c.client_id)
    expect(new Set(ids).size).toBe(3)
  })
})

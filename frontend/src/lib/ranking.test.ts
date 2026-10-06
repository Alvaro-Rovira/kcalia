import { describe, expect, it } from 'vitest'
import { rankForSlot, slotScore } from './ranking'

const NOW = Date.parse('2026-10-06T08:00:00Z')
const daysAgo = (n: number) => new Date(NOW - n * 86_400_000).toISOString()

const cafe = { name: 'café', use_count: 30, last_used_at: daysAgo(0), slot_counts: { desayuno: 26, merienda: 4 } }
const cena = { name: 'tortilla', use_count: 12, last_used_at: daysAgo(1), slot_counts: { cena: 12 } }
const yogur = { name: 'yogur', use_count: 10, last_used_at: daysAgo(2), slot_counts: { merienda: 6, snack: 4 } }

describe('rankForSlot', () => {
  it('por la mañana manda el desayuno y por la noche la cena', () => {
    expect(rankForSlot([cena, yogur, cafe], 'desayuno', NOW)[0].name).toBe('café')
    expect(rankForSlot([cafe, yogur, cena], 'cena', NOW)[0].name).toBe('tortilla')
    expect(rankForSlot([cafe, cena, yogur], 'merienda', NOW)[0].name).toBe('yogur')
  })
  it('sin historial por momentos, cuentan el uso y lo reciente', () => {
    const viejo = { name: 'viejo', use_count: 2, last_used_at: daysAgo(90) }
    const nuevo = { name: 'nuevo', use_count: 2, last_used_at: daysAgo(0) }
    expect(rankForSlot([viejo, nuevo], 'comida', NOW).map((d) => d.name)).toEqual(['nuevo', 'viejo'])
  })
  it('una sola vez en un momento no pesa más que una costumbre', () => {
    const una = { use_count: 1, last_used_at: daysAgo(0), slot_counts: { comida: 1 } }
    const costumbre = { use_count: 20, last_used_at: daysAgo(3), slot_counts: { comida: 18, cena: 2 } }
    expect(slotScore(costumbre, 'comida', NOW)).toBeGreaterThan(slotScore(una, 'comida', NOW))
  })
  it('es estable y no pierde elementos', () => {
    const a = { id: 1, use_count: 0, last_used_at: 'x' }
    const b = { id: 2, use_count: 0, last_used_at: 'x' }
    expect(rankForSlot([a, b], 'snack', NOW).map((x) => x.id)).toEqual([1, 2])
  })
})

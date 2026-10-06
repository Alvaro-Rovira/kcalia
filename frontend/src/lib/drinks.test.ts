import { describe, expect, it } from 'vitest'
import { alcoholGrams, DRINKS, drinkItem } from './drinks'

describe('bebidas con alcohol', () => {
  it('una caña: 7,9 g de alcohol y sus calorías', () => {
    const item = drinkItem(DRINKS.find((d) => d.key === 'cana')!)
    expect(item.alcohol).toBe(7.9)
    // 7,89 g × 7 + 7,2 g HC × 4 + 0,8 g P × 4 = 87,2
    expect(item.kcal).toBe(87.2)
    expect(item).toMatchObject({ unit: 'ml', grams: 200, carbs: 7.2, fat: 0 })
  })
  it('un chupito es casi todo alcohol', () => {
    const item = drinkItem(DRINKS.find((d) => d.key === 'chupito')!)
    expect(item.alcohol).toBe(12.6)
    expect(item.kcal).toBe(88.4)
  })
  it('gramos de alcohol según volumen y graduación', () => {
    expect(alcoholGrams(150, 13.5)).toBeCloseTo(15.98, 2)
    expect(alcoholGrams(330, 0)).toBe(0)
  })
  it('todas las bebidas tienen alcohol y calorías coherentes', () => {
    for (const drink of DRINKS) {
      const item = drinkItem(drink)
      expect(item.alcohol).toBeGreaterThan(0)
      expect(item.kcal).toBeGreaterThanOrEqual(item.alcohol! * 7 - 0.1)
    }
  })
})

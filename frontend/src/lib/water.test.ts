import { describe, expect, it } from 'vitest'
import { autoWaterGoal, fmtWater } from './water'

describe('agua', () => {
  it('objetivo automático igual que el servidor', () => {
    expect(autoWaterGoal(61)).toBe(2250)
    expect(autoWaterGoal(80)).toBe(2750)
    expect(autoWaterGoal(30)).toBe(1500)
    expect(autoWaterGoal(150)).toBe(4000)
    expect(autoWaterGoal(null)).toBe(2000)
  })
  it('formato en ml o litros', () => {
    expect(fmtWater(250)).toBe('250 ml')
    expect(fmtWater(1250)).toBe('1,25 L')
    expect(fmtWater(2000)).toBe('2 L')
  })
})

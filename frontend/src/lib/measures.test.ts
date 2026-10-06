import { describe, expect, it } from 'vitest'
import { lastKnown, measureSeries } from './measures'
import type { Measurement } from './types'

const entries: Measurement[] = [
  { date: '2026-09-01', waist: 84, chest: null, arm: 32, hip: null, thigh: null },
  { date: '2026-09-15', waist: null, chest: 100, arm: null, hip: null, thigh: null },
  { date: '2026-10-01', waist: 81.5, chest: null, arm: 33, hip: null, thigh: null },
]

describe('medidas', () => {
  it('serie y cambio de una medida, saltando los días sin ella', () => {
    const waist = measureSeries(entries, 'waist')
    expect(waist.points.map((p) => p.value)).toEqual([84, 81.5])
    expect(waist.change).toBe(-2.5)
    expect(measureSeries(entries, 'chest').change).toBeNull()
    expect(measureSeries(entries, 'hip').latest).toBeNull()
  })
  it('último valor conocido de cada medida', () => {
    expect(lastKnown(entries)).toEqual({ waist: 81.5, chest: 100, arm: 33 })
  })
})

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { cardioMinutes, estimatedKcal, type Intensity } from './training'

// Los mismos casos que el backend: los dos lados deben calcular igual.
const fixture = fileURLToPath(new URL('../../../backend/tests/fixtures/exercise_kcal_cases.json', import.meta.url))
const cases = JSON.parse(readFileSync(fixture, 'utf8')) as { minutes: number; intensity: Intensity; weight: number; cardio: Record<string, number>; kcal: number }[]

describe('calorías netas del entreno', () => {
  it.each(cases)('$minutes min $intensity, $weight kg, cardio $cardio', (c) => {
    expect(estimatedKcal(c.minutes, c.intensity, c.weight, c.cardio)).toBe(c.kcal)
  })

  it('suma los minutos de los ejercicios de cardio de la sesión', () => {
    const sets = [
      { exercise: 'ex-cinta', reps: 10 },
      { exercise: 'ex-press-banca', reps: 8 },
      { exercise: 'ex-cinta', reps: 15 },
    ]
    expect(cardioMinutes(sets, new Set(['ex-cinta']))).toEqual({ 'ex-cinta': 25 })
  })
})

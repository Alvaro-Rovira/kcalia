import { describe, expect, it } from 'vitest'
import { activityFor, DAY_OPTIONS, TRAINING_OPTIONS } from './activity'
import { ACTIVITIES } from './options'

const factor = (value: string) => ACTIVITIES.find((a) => a.value === value)!.factor

describe('nivel de actividad a partir de dos preguntas', () => {
  it('estudiante sentado que entrena 4 días: Medio (ni Ligero, que se queda corto, ni Moderado, que se pasa)', () => {
    expect(activityFor('sentado', '4-5')).toBe('medio')
  })

  it('casos claros', () => {
    expect(activityFor('sentado', '0')).toBe('sedentario')
    expect(activityFor('de_pie', '4-5')).toBe('moderado')
    expect(activityFor('fisico', '6-7')).toBe('muy_alto')
  })

  it('más movimiento o más días de entreno nunca bajan el factor', () => {
    for (const day of DAY_OPTIONS) {
      const factors = TRAINING_OPTIONS.map((t) => factor(activityFor(day.value, t.value)))
      expect([...factors].sort((a, b) => a - b)).toEqual(factors)
    }
    for (const training of TRAINING_OPTIONS) {
      const factors = DAY_OPTIONS.map((d) => factor(activityFor(d.value, training.value)))
      expect([...factors].sort((a, b) => a - b)).toEqual(factors)
    }
  })
})

import { describe, expect, it } from 'vitest'
import { activeWorkout, estimated1rm, estimatedKcal, fmtElapsed, fmtSet, nextSet, sessionExercises, volumeOf, type WorkoutSession } from './training'

const set = (exercise: string, position: number, weight: number, reps: number) => ({ client_id: `${exercise}-${position}`, exercise, position, weight, reps, rpe: null, created_at: `2026-10-01T18:0${position}:00Z` })
const session = (over: Partial<WorkoutSession> = {}): WorkoutSession => ({
  client_id: 'wk', date: '2026-10-01', name: 'Empuje', notes: '', template_cid: 'tpl', started_at: '2026-10-01T18:00:00Z', ended_at: null,
  duration_min: null, intensity: 'moderada', kcal: 0, volume: 0, sets: [], ...over,
})

describe('entrenos', () => {
  it('1RM y calorías iguales que el servidor', () => {
    expect(estimated1rm(100, 1)).toBe(100)
    expect(estimated1rm(80, 8)).toBeCloseTo(101.3, 1)
    expect(estimated1rm(50, 20)).toBe(estimated1rm(50, 12))
    expect(estimatedKcal(60, 'moderada', 80)).toBe(400)
    expect(estimatedKcal(45, 'intensa', 70)).toBe(315)
  })
  it('volumen y formato de series', () => {
    expect(volumeOf([set('a', 0, 80, 8), set('a', 1, 85, 6)])).toBe(1150)
    expect(fmtSet(82.5, 8)).toBe('82,5 kg × 8')
    expect(fmtSet(0, 12)).toBe('12 reps')
    expect(fmtSet(0, 45, 'seg')).toBe('45 seg')
    expect(fmtElapsed(3_725_000)).toBe('1:02:05')
    expect(fmtElapsed(65_000)).toBe('1:05')
  })
  it('ejercicios de la sesión: plantilla, con series y añadidos, sin repetir', () => {
    const template = { client_id: 'tpl', name: 'Empuje', position: 0, exercises: [{ exercise: 'banca', sets: 4, reps: 8 }, { exercise: 'militar', sets: 3, reps: 8 }] }
    const s = session({ sets: [set('fondos', 0, 0, 12), set('banca', 1, 80, 8)] })
    const list = sessionExercises(s, template, ['curl', 'banca'])
    expect(list.map((e) => e.exercise)).toEqual(['banca', 'militar', 'fondos', 'curl'])
    expect(list[0].plan?.sets).toBe(4)
    expect(list[0].sets).toHaveLength(1)
    expect(list[3].sets).toHaveLength(0)
  })
  it('siguiente serie: copia la anterior, si no la última vez, si no la plantilla', () => {
    expect(nextSet(set('a', 0, 80, 8), { date: 'x', weight: 70, reps: 10, sets: 3 }, null)).toEqual({ weight: 80, reps: 8 })
    expect(nextSet(undefined, { date: 'x', weight: 70, reps: 10, sets: 3 }, null)).toEqual({ weight: 70, reps: 10 })
    expect(nextSet(undefined, undefined, { exercise: 'a', sets: 3, reps: 12 })).toEqual({ weight: 0, reps: 12 })
  })
  it('sesión en curso: sin terminar y reciente', () => {
    const now = Date.parse('2026-10-01T19:00:00Z')
    expect(activeWorkout([session()], now)?.client_id).toBe('wk')
    expect(activeWorkout([session({ ended_at: '2026-10-01T18:50:00Z' })], now)).toBeNull()
    expect(activeWorkout([session()], Date.parse('2026-10-02T09:00:00Z'))).toBeNull()
  })
})

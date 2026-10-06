import { describe, expect, it } from 'vitest'
import { shareLines, shareText } from './shareCard'
import type { WeekSummary } from './types'

const week = {
  week_start: '2026-09-28', week_end: '2026-10-04', adherence_pct: 71, avg_kcal: 2140, avg_protein: 148, logged_days: 6,
  weight: { avg: 79.4, previous_avg: 80, change: -0.6, entries: 4 },
} as unknown as WeekSummary

describe('compartir el resumen', () => {
  it('cifras clave con formato es-ES', () => {
    expect(shareLines(week)).toEqual([
      { label: 'Adherencia', value: '71 %' },
      { label: 'Media diaria', value: '2.140 kcal' },
      { label: 'Proteína media', value: '148 g' },
      { label: 'Días registrados', value: '6 de 7' },
      { label: 'Peso', value: '−0,6 kg' },
    ])
  })
  it('sin cambio de peso, el peso medio; sin pesadas, nada', () => {
    expect(shareLines({ ...week, weight: { avg: 79.4, previous_avg: null, change: null, entries: 2 } }).at(-1)).toEqual({ label: 'Peso medio', value: '79,4 kg' })
    expect(shareLines({ ...week, weight: { avg: null, previous_avg: null, change: null, entries: 0 } })).toHaveLength(4)
  })
  it('texto que acompaña a la imagen', () => {
    expect(shareText(week)).toBe('Mi semana con Kcalia (28 sept – 4 oct): adherencia 71 %, media diaria 2.140 kcal, proteína media 148 g, días registrados 6 de 7, peso −0,6 kg.')
  })
})

import type { MeasureKey, Measurement } from './types'

export const MEASURES: { key: MeasureKey; label: string; hint: string }[] = [
  { key: 'waist', label: 'Cintura', hint: 'A la altura del ombligo, sin apretar' },
  { key: 'chest', label: 'Pecho', hint: 'Por la parte más ancha' },
  { key: 'arm', label: 'Brazo', hint: 'Bíceps relajado, por la parte más ancha' },
  { key: 'hip', label: 'Cadera', hint: 'Por la parte más ancha de los glúteos' },
  { key: 'thigh', label: 'Muslo', hint: 'Por la parte más ancha, siempre la misma pierna' },
]

export const EMPTY_MEASUREMENT = (date: string): Measurement => ({ date, waist: null, chest: null, arm: null, hip: null, thigh: null })

/** Serie de una medida (solo los días en que se apuntó) y su cambio desde la primera. */
export function measureSeries(entries: Measurement[], key: MeasureKey) {
  const points = entries.filter((e) => e[key] !== null).map((e) => ({ date: e.date, value: e[key] as number }))
  const change = points.length >= 2 ? Math.round((points[points.length - 1].value - points[0].value) * 10) / 10 : null
  return { points, latest: points[points.length - 1] ?? null, change }
}

/** Último valor conocido de cada medida: para rellenar el formulario de hoy. */
export function lastKnown(entries: Measurement[]): Partial<Record<MeasureKey, number>> {
  const out: Partial<Record<MeasureKey, number>> = {}
  for (const entry of entries) for (const { key } of MEASURES) if (entry[key] !== null) out[key] = entry[key] as number
  return out
}

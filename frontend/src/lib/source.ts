import type { Item } from './types'

/** De dónde salen los valores de un ingrediente (como `refine.py` en el servidor). */
export type ValueSource = 'tabla' | 'etiqueta' | 'manual' | 'ia'

export const SOURCE_LABEL: Record<ValueSource, string> = {
  tabla: 'Valores oficiales de la tabla de alimentos',
  etiqueta: 'De la etiqueta de tu producto',
  manual: 'Valores puestos por ti',
  ia: 'Valores estimados por la IA',
}

/** Lo antiguo no trae origen: si no es de una etiqueta ni se añadió a mano, lo estimó la IA. */
export function sourceOf(item: Item): ValueSource {
  if (item.product_id || item.source === 'etiqueta') return 'etiqueta'
  if (item.source === 'tabla') return 'tabla'
  if (item.manual || item.source === 'manual' || item.source === 'usuario') return 'manual'
  return 'ia'
}

/** Parte de las kcal (0 a 1) con valores oficiales, de una etiqueta o puestos por el usuario. */
export function officialShare(items: Item[]): number {
  const total = items.reduce((sum, i) => sum + (i.kcal || 0), 0)
  if (total <= 0) return 0
  const official = items.reduce((sum, i) => sum + (sourceOf(i) === 'ia' ? 0 : i.kcal || 0), 0)
  return Math.round((official / total) * 1000) / 1000
}

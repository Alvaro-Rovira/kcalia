/** Atajos que llegan por la URL: los de la PWA instalada y el atajo de voz de iPhone. */

export const SHORTCUT_PARAMS = ['nueva', 'texto', 'agua'] as const
const MAX_TEXT = 600

export interface Shortcut {
  /** Abrir la hoja de añadir comida. */
  add: boolean
  /** Texto ya escrito en la hoja (dictado). Nunca se analiza solo. */
  text: string
  /** Mililitros de agua que apuntar hoy, o null. */
  waterMl: number | null
}

export function readShortcut(params: URLSearchParams): Shortcut | null {
  if (!SHORTCUT_PARAMS.some((key) => params.has(key))) return null
  const add = params.get('nueva') === '1'
  const raw = Number(params.get('agua'))
  const waterMl = params.has('agua') && Number.isInteger(raw) && raw >= 50 && raw <= 1000 ? raw : null
  const text = add ? (params.get('texto') ?? '').replace(/\s+/g, ' ').trim().slice(0, MAX_TEXT) : ''
  return { add, text, waterMl }
}

/** La URL sin los parámetros de atajo (el resto, como ?fecha=, se conserva). */
export function withoutShortcut(params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(params)
  for (const key of SHORTCUT_PARAMS) next.delete(key)
  return next
}

/** Dirección que abre la hoja de añadir con el texto dictado detrás. */
export function voiceShortcutUrl(origin: string): string {
  return `${origin.replace(/\/$/, '')}/?nueva=1&texto=`
}

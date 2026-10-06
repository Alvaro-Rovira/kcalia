/** Vibración corta donde exista (Android); en iOS no hace nada y no pasa nada. */
const patterns = {
  tap: 8,
  select: 12,
  success: [14, 50, 22],
  warning: [24, 60, 24],
  error: [40, 40, 40],
} as const

export function haptic(kind: keyof typeof patterns = 'tap'): void {
  // Sin un toque previo en la página (p. ej. al abrir un atajo) Chrome bloquea la vibración y lo anota como error.
  if (typeof navigator === 'undefined' || navigator.userActivation?.hasBeenActive === false) return
  try {
    navigator.vibrate?.(patterns[kind] as number | number[])
  } catch {
    // Algunos navegadores lanzan si no hubo interacción previa.
  }
}

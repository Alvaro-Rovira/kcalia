import type { ThemePref } from './types'

const KEY = 'kcalia:theme'

declare global {
  interface Window {
    __kcaliaApplyTheme?: () => void
  }
}

export function getThemePref(): ThemePref {
  try {
    const value = localStorage.getItem(KEY)
    if (value === 'light' || value === 'dark' || value === 'auto') return value
  } catch {
    // Almacenamiento bloqueado (modo privado): se usa el predeterminado.
  }
  return 'dark'
}

export function setThemePref(pref: ThemePref): void {
  try {
    localStorage.setItem(KEY, pref)
  } catch {
    // Sin almacenamiento el cambio vale solo para esta sesión.
  }
  // theme.js (cargado antes del primer pintado) es quien sabe aplicar el tema.
  window.__kcaliaApplyTheme?.()
}

/** Objetivo automático de agua: 35 ml por kg, redondeado a 250 ml, entre 1,5 y 4 litros (como el servidor). */
export function autoWaterGoal(weightKg: number | null | undefined): number {
  if (!weightKg) return 2000
  return Math.min(4000, Math.max(1500, Math.round((weightKg * 35) / 250) * 250))
}

/** «750 ml» o «1,25 L». */
export function fmtWater(ml: number): string {
  if (ml < 1000) return `${Math.round(ml)} ml`
  const liters = Math.round(ml / 10) / 100
  return `${liters.toLocaleString('es-ES', { maximumFractionDigits: 2 })} L`
}

export const WATER_QUICK = [250, 500] as const

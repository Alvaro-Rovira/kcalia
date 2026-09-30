import { fmt } from './format'
import type { Macros, Targets } from './types'

export interface Tip {
  text: string
  tone: 'kcal' | 'protein' | 'neutral' | 'warn'
}

function proteinIdea(grams: number): string {
  if (grams <= 12) return 'un yogur proteico y listo'
  if (grams <= 22) return 'un yogur griego con un puñado de nueces y listo'
  if (grams <= 32) return 'una lata de atún o 120 g de pavo y listo'
  if (grams <= 45) return 'una pechuga de pollo (150 g) lo cubre'
  return 'repártelos en dos tomas con carne, pescado o huevos'
}

function nextMeal(hour: number): string {
  if (hour < 12) return 'la comida'
  if (hour < 17) return 'la merienda y la cena'
  if (hour < 21) return 'la cena'
  return 'lo que queda de día'
}

/** Mensaje contextual de la pantalla de hoy: qué falta y cómo cubrirlo. */
export function dailyTip(eaten: Macros, targets: Targets, meals: number, isToday: boolean, now = new Date()): Tip {
  const remainingKcal = targets.kcal - eaten.kcal
  const remainingProtein = targets.protein - eaten.protein
  const proteinDone = eaten.protein >= targets.protein * 0.9
  const kcalRatio = eaten.kcal / targets.kcal

  if (meals === 0) {
    return isToday
      ? { text: 'Día en blanco. Cuéntame qué has comido y yo hago las cuentas.', tone: 'neutral' }
      : { text: 'No hay nada apuntado este día.', tone: 'neutral' }
  }
  if (kcalRatio > 1.1) {
    return {
      text: `Te has pasado ${fmt(-remainingKcal)} kcal. No pasa nada: un día no cambia la tendencia.`,
      tone: 'warn',
    }
  }
  if (kcalRatio >= 0.9 && proteinDone) {
    return { text: 'Día redondo: calorías y proteína en su sitio.', tone: 'kcal' }
  }
  if (!proteinDone && remainingProtein >= 8) {
    // Con pocas calorías de margen, la proteína que falta tiene que venir de algo magro.
    const tight = remainingKcal < remainingProtein * 6
    return {
      text: tight
        ? `Te quedan ${fmt(remainingProtein)} g de proteína y poco margen de calorías: tira de algo magro, como claras, pavo o queso batido.`
        : `Te quedan ${fmt(remainingProtein)} g de proteína: ${proteinIdea(remainingProtein)}.`,
      tone: 'protein',
    }
  }
  if (kcalRatio >= 0.9) {
    return { text: 'Calorías en objetivo. Buen trabajo.', tone: 'kcal' }
  }
  if (!isToday) {
    return { text: `Te quedaste ${fmt(remainingKcal)} kcal por debajo del objetivo.`, tone: 'neutral' }
  }
  return {
    text: `Proteína cumplida. Te quedan ${fmt(remainingKcal)} kcal para ${nextMeal(now.getHours())}.`,
    tone: 'kcal',
  }
}

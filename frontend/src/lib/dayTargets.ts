/**
 * Objetivos según el tipo de día (entreno o descanso). Espejo de backend/app/daytargets.py, probado con el mismo
 * fichero de casos (backend/tests/fixtures/day_target_cases.json): si cambias uno, cambia el otro.
 */
import { parseISO } from './dates'
import type { DayKind, DayTargetsValues, Prefs } from './types'

export const DEFAULT_TRAINING_DAYS = [0, 2, 4]
export const DEFAULT_TRAINING_ADJUST = 200
export const DEFAULT_REST_ADJUST = -100

const round = (value: number) => Math.floor(value + 0.5)

/** 0 = lunes … 6 = domingo, como en Python. */
export const weekdayIndex = (iso: string) => (parseISO(iso).getDay() + 6) % 7

export function kindFor(iso: string, prefs: Partial<Prefs> | undefined, overrides: Record<string, DayKind> = {}): DayKind | null {
  if (!prefs?.day_types) return null
  const override = overrides[iso]
  if (override === 'entreno' || override === 'descanso') return override
  return (prefs.training_days ?? DEFAULT_TRAINING_DAYS).includes(weekdayIndex(iso)) ? 'entreno' : 'descanso'
}

const trainingCount = (prefs: Partial<Prefs> | undefined) => new Set(prefs?.training_days ?? DEFAULT_TRAINING_DAYS).size

/** Los días de descanso compensan los de entreno salvo que se haya desactivado. */
export const balancesRest = (prefs: Partial<Prefs> | undefined) => prefs?.balance_rest !== false

/** Calorías que se suman los días de entreno. Si se entrena a diario no hay días con los que compensar: ninguna. */
export function trainingAdjust(prefs: Partial<Prefs> | undefined): number {
  if (balancesRest(prefs) && trainingCount(prefs) === 7) return 0
  return prefs?.training_kcal_adjust ?? DEFAULT_TRAINING_ADJUST
}

/** Calorías de los días de descanso: compensando, lo que suben los de entreno repartido entre ellos (a 10 kcal). */
export function restAdjust(baseKcal: number, prefs: Partial<Prefs> | undefined): number {
  if (!balancesRest(prefs)) return prefs?.rest_kcal_adjust ?? DEFAULT_REST_ADJUST
  const training = trainingCount(prefs)
  if (training === 0 || training === 7) return 0
  const extra = prefs?.training_targets ? prefs.training_targets.kcal - round(baseKcal) : (prefs?.training_kcal_adjust ?? DEFAULT_TRAINING_ADJUST)
  return round((-extra * training) / (7 - training) / 10) * 10
}

function shift(values: DayTargetsValues, kcalDelta: number): DayTargetsValues {
  const carbs = Math.max(0, round(values.carbs + kcalDelta / 4))
  return { ...values, carbs, kcal: round(values.kcal + (carbs - values.carbs) * 4) }
}

/** `measured`: el mantenimiento es el gasto real medido, que ya incluye los entrenos; no se suman otra vez. */
export function targetsFor(base: DayTargetsValues, prefs: Partial<Prefs> | undefined, kind: DayKind | null, exerciseKcal = 0, measured = false): DayTargetsValues {
  let out: DayTargetsValues = { kcal: round(base.kcal), protein: round(base.protein), carbs: round(base.carbs), fat: round(base.fat) }
  if (kind === 'entreno') out = prefs?.training_targets ? { ...prefs.training_targets } : shift(out, trainingAdjust(prefs))
  else if (kind === 'descanso') out = prefs?.rest_targets ? { ...prefs.rest_targets } : shift(out, restAdjust(base.kcal, prefs))
  if (prefs?.add_exercise_kcal && exerciseKcal > 0 && !measured) out = shift(out, exerciseKcal)
  return out
}

export const KIND_LABEL: Record<DayKind, string> = { entreno: 'Día de entreno', descanso: 'Día de descanso' }

const WEEKDAY_NAMES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

/** Días de entreno habituales en palabras: «lunes, miércoles y viernes». 0 = lunes. */
export function trainingDaysText(days: number[]): string {
  const names = [...new Set(days)].sort((a, b) => a - b).map((day) => WEEKDAY_NAMES[day])
  if (!names.length) return 'ningún día'
  if (names.length === 7) return 'todos los días'
  return names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} y ${names[names.length - 1]}`
}

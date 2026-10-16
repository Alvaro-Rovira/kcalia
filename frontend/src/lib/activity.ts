import type { Activity } from './types'

/**
 * El nivel de actividad sale de dos preguntas sencillas en lugar de una lista: el factor depende del día entero (lo que
 * se mueve uno fuera del gimnasio) y de los días de entreno, y elegirlo «a ojo» de una lista llevaba a equivocarse.
 */
export type DayAnswer = 'sentado' | 'de_pie' | 'fisico'
export type TrainingAnswer = '0' | '1-3' | '4-5' | '6-7'

export const DAY_OPTIONS: { value: DayAnswer; label: string; text: string }[] = [
  { value: 'sentado', label: 'Sentado casi todo el día', text: 'Estudio, oficina, teletrabajo, coche' },
  { value: 'de_pie', label: 'De pie o andando buena parte del día', text: 'Dependiente, camarero, docente, más de 10.000 pasos' },
  { value: 'fisico', label: 'Trabajo físico', text: 'Obra, almacén, campo, reparto a pie' },
]

export const TRAINING_OPTIONS: { value: TrainingAnswer; label: string }[] = [
  { value: '0', label: 'Ninguno' },
  { value: '1-3', label: '1-3 días' },
  { value: '4-5', label: '4-5 días' },
  { value: '6-7', label: '6-7 días' },
]

const TABLE: Record<DayAnswer, [Activity, Activity, Activity, Activity]> = {
  sentado: ['sedentario', 'ligero', 'medio', 'moderado'],
  de_pie: ['ligero', 'medio', 'moderado', 'alto'],
  fisico: ['moderado', 'alto', 'alto', 'muy_alto'],
}

export function activityFor(day: DayAnswer, training: TrainingAnswer): Activity {
  return TABLE[day][TRAINING_OPTIONS.findIndex((o) => o.value === training)]
}

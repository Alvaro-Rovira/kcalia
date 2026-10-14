/** Entrenamientos en el móvil: tipos y cálculos (1RM estimado, volumen, siguiente serie). Sin IA. */

export type Muscle = 'pecho' | 'espalda' | 'hombros' | 'biceps' | 'triceps' | 'piernas' | 'gluteos' | 'core' | 'cardio' | 'otro'
export type ExerciseUnit = 'reps' | 'seg' | 'min'
export type Intensity = 'suave' | 'moderada' | 'intensa'

export interface Exercise {
  id?: number
  client_id: string
  name: string
  muscle: Muscle
  unit: ExerciseUnit
  custom: boolean
  archived: boolean
}

export interface TemplateExercise {
  exercise: string
  sets: number
  reps: number
}

export interface WorkoutTemplate {
  client_id: string
  name: string
  exercises: TemplateExercise[]
  position: number
}

export interface WorkoutSetRow {
  client_id: string
  exercise: string
  position: number
  reps: number
  weight: number
  rpe: number | null
  created_at: string
  pending?: boolean
}

export interface WorkoutSession {
  client_id: string
  date: string
  name: string
  notes: string
  template_cid: string | null
  started_at: string
  ended_at: string | null
  duration_min: number | null
  intensity: Intensity
  kcal: number
  volume: number
  sets: WorkoutSetRow[]
  pending?: boolean
}

export interface LastPerformance {
  date: string
  weight: number
  reps: number
  sets: number
}

export interface TrainingData {
  exercises: Exercise[]
  templates: WorkoutTemplate[]
  workouts: WorkoutSession[]
  last: Record<string, LastPerformance>
}

export const MUSCLES: { key: Muscle; label: string }[] = [
  { key: 'pecho', label: 'Pecho' },
  { key: 'espalda', label: 'Espalda' },
  { key: 'hombros', label: 'Hombros' },
  { key: 'biceps', label: 'Bíceps' },
  { key: 'triceps', label: 'Tríceps' },
  { key: 'piernas', label: 'Piernas' },
  { key: 'gluteos', label: 'Glúteos' },
  { key: 'core', label: 'Core' },
  { key: 'cardio', label: 'Cardio' },
  { key: 'otro', label: 'Otro' },
]
export const MUSCLE_LABEL = Object.fromEntries(MUSCLES.map((m) => [m.key, m.label])) as Record<Muscle, string>
export const UNIT_LABEL: Record<ExerciseUnit, string> = { reps: 'reps', seg: 'seg', min: 'min' }

/** MET de fuerza según la intensidad, como el servidor (Compendium of Physical Activities 2024). */
export const MET: Record<Intensity, number> = { suave: 3.5, moderada: 5, intensa: 6 }
/** MET del cardio del catálogo (ejercicios en minutos), como el servidor (backend/app/workouts.py). */
export const CARDIO_MET: Record<string, Record<Intensity, number>> = {
  'ex-cinta': { suave: 7.5, moderada: 8.5, intensa: 9.3 },
  'ex-bici': { suave: 5.8, moderada: 6, intensa: 8 },
  'ex-remo-ergometro': { suave: 5, moderada: 7.5, intensa: 11 },
  'ex-eliptica': { suave: 5, moderada: 5, intensa: 9 },
}
const GENERIC_CARDIO_MET = CARDIO_MET['ex-bici']
const RESTING_MET = 1

/** Fórmula de Epley (como el servidor): con 1 repetición, el propio peso; más allá de 12, no sube. */
export function estimated1rm(weight: number, reps: number): number {
  if (weight <= 0 || reps <= 0) return 0
  if (reps === 1) return Math.round(weight * 10) / 10
  return Math.round(weight * (1 + Math.min(reps, 12) / 30) * 10) / 10
}

/**
 * Calorías netas del entreno, como el servidor: (MET − 1) × kg × horas. Se resta el gasto en reposo porque el
 * objetivo del día ya lo cuenta. Los minutos de cardio usan el MET de su actividad; el resto, el de fuerza.
 */
export function estimatedKcal(minutes: number | null, intensity: Intensity, weightKg: number, cardio: Record<string, number> = {}): number {
  if (!minutes) return 0
  const level: Intensity = intensity in MET ? intensity : 'moderada'
  const entries = Object.entries(cardio).filter(([, m]) => m > 0)
  const cardioTotal = entries.reduce((sum, [, m]) => sum + m, 0)
  const scale = cardioTotal ? Math.min(1, minutes / cardioTotal) : 1
  let kcal = 0
  for (const [exercise, m] of entries) {
    const met = (CARDIO_MET[exercise] ?? GENERIC_CARDIO_MET)[level]
    kcal += ((met - RESTING_MET) * weightKg * m * scale) / 60
  }
  const strength = Math.max(0, minutes - cardioTotal * scale)
  kcal += ((MET[level] - RESTING_MET) * weightKg * strength) / 60
  return Math.round(kcal)
}

/** Minutos por ejercicio de cardio (los que se miden en minutos) a partir de las series de la sesión. */
export function cardioMinutes(sets: { exercise: string; reps: number }[], minuteExercises: Set<string>): Record<string, number> {
  const out: Record<string, number> = {}
  for (const set of sets) {
    if (minuteExercises.has(set.exercise)) out[set.exercise] = (out[set.exercise] ?? 0) + set.reps
  }
  return out
}

export const volumeOf = (sets: WorkoutSetRow[]) => Math.round(sets.reduce((sum, s) => sum + s.weight * s.reps, 0) * 10) / 10

/** Sesión en curso: la última sin terminar de las últimas 12 horas. */
export function activeWorkout(workouts: WorkoutSession[], now = Date.now()): WorkoutSession | null {
  return workouts.find((w) => !w.ended_at && now - Date.parse(w.started_at) < 12 * 3_600_000) ?? null
}

/**
 * Ejercicios de una sesión, en orden: los de su plantilla, los que ya tienen series y los añadidos a mano.
 * Cada uno con sus series y, si viene de plantilla, las series y repeticiones previstas.
 */
export function sessionExercises(session: WorkoutSession, template: WorkoutTemplate | undefined, extra: string[] = []) {
  const order: string[] = []
  const plan = new Map<string, TemplateExercise>()
  for (const item of template?.exercises ?? []) {
    if (!plan.has(item.exercise)) order.push(item.exercise)
    plan.set(item.exercise, item)
  }
  for (const set of [...session.sets].sort((a, b) => a.position - b.position)) if (!order.includes(set.exercise)) order.push(set.exercise)
  for (const cid of extra) if (!order.includes(cid)) order.push(cid)
  return order.map((exercise) => ({
    exercise,
    plan: plan.get(exercise) ?? null,
    sets: session.sets.filter((s) => s.exercise === exercise).sort((a, b) => a.position - b.position || a.created_at.localeCompare(b.created_at)),
  }))
}

/** Lo que se propone para la siguiente serie: copia la anterior; si no hay, la última vez; si no, la plantilla. */
export function nextSet(previous: WorkoutSetRow | undefined, last: LastPerformance | undefined, plan: TemplateExercise | null): { weight: number; reps: number } {
  if (previous) return { weight: previous.weight, reps: previous.reps }
  if (last) return { weight: last.weight, reps: last.reps }
  return { weight: 0, reps: plan?.reps ?? 10 }
}

/** «82,5 kg × 8», «45 seg», «20 min». */
export function fmtSet(weight: number, reps: number, unit: ExerciseUnit = 'reps'): string {
  if (unit !== 'reps') return `${reps} ${UNIT_LABEL[unit]}${weight > 0 ? ` · ${String(weight).replace('.', ',')} kg` : ''}`
  return weight > 0 ? `${String(weight).replace('.', ',')} kg × ${reps}` : `${reps} reps`
}

export function fmtElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}

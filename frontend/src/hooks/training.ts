import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { api, newClientId } from '@/lib/api'
import { todayISO } from '@/lib/dates'
import {
  volumeOf,
  type Exercise,
  type ExerciseUnit,
  type Intensity,
  type Muscle,
  type TemplateExercise,
  type TrainingData,
  type WorkoutSession,
  type WorkoutSetRow,
} from '@/lib/training'
import { enqueue } from '@/offline/outbox'
import { keys } from '@/offline/queryClient'

export function useTraining() {
  return useQuery({ queryKey: keys.training, queryFn: () => api.get<TrainingData>('/api/training') })
}

export function useExerciseHistory(cid: string | null) {
  return useQuery({
    queryKey: keys.exerciseHistory(cid ?? ''),
    queryFn: () =>
      api.get<{ sessions: { date: string; best_1rm: number; volume: number; top_weight: number; top_reps: number }[] }>(
        `/api/exercises/${cid}/history?days=3650`,
      ),
    enabled: !!cid,
  })
}

/** Escrituras de entreno: se ven al instante y viajan por la cola offline, cada una con su client_id. */
export function useTrainingActions() {
  const client = useQueryClient()

  const update = useCallback(
    (change: (data: TrainingData) => TrainingData) =>
      client.setQueryData<TrainingData>(keys.training, (old) => change(old ?? { exercises: [], templates: [], workouts: [], last: {} })),
    [client],
  )

  const patchWorkout = useCallback(
    (cid: string, change: (w: WorkoutSession) => WorkoutSession) =>
      update((data) => ({
        ...data,
        workouts: data.workouts.map((w) => {
          if (w.client_id !== cid) return w
          const next = change(w)
          return { ...next, volume: volumeOf(next.sets) }
        }),
      })),
    [update],
  )

  const start = useCallback(
    (name: string, templateCid: string | null = null): WorkoutSession => {
      const session: WorkoutSession = {
        client_id: newClientId(),
        date: todayISO(),
        name,
        notes: '',
        template_cid: templateCid,
        started_at: new Date().toISOString(),
        ended_at: null,
        duration_min: null,
        intensity: 'moderada',
        kcal: 0,
        volume: 0,
        sets: [],
        pending: true,
      }
      update((data) => ({ ...data, workouts: [session, ...data.workouts] }))
      void enqueue({
        type: 'workout.create',
        body: { client_id: session.client_id, date: session.date, name, template_cid: templateCid, started_at: session.started_at },
      })
      return session
    },
    [update],
  )

  const addSet = useCallback(
    (workoutCid: string, exercise: string, weight: number, reps: number, rpe: number | null = null) => {
      let position = 0
      const row: WorkoutSetRow = { client_id: newClientId(), exercise, weight, reps, rpe, position, created_at: new Date().toISOString(), pending: true }
      patchWorkout(workoutCid, (w) => {
        position = w.sets.length ? Math.max(...w.sets.map((s) => s.position)) + 1 : 0
        return { ...w, sets: [...w.sets, { ...row, position }] }
      })
      void enqueue({ type: 'set.create', workoutId: workoutCid, body: { client_id: row.client_id, exercise, weight, reps, rpe, position } })
      return row
    },
    [patchWorkout],
  )

  const updateSet = useCallback(
    (workoutCid: string, setCid: string, body: { reps?: number; weight?: number; rpe?: number | null }) => {
      patchWorkout(workoutCid, (w) => ({ ...w, sets: w.sets.map((s) => (s.client_id === setCid ? { ...s, ...body } : s)) }))
      void enqueue({ type: 'set.patch', clientId: setCid, body })
    },
    [patchWorkout],
  )

  const removeSet = useCallback(
    (workoutCid: string, setCid: string) => {
      patchWorkout(workoutCid, (w) => ({ ...w, sets: w.sets.filter((s) => s.client_id !== setCid) }))
      void enqueue({ type: 'set.delete', clientId: setCid })
    },
    [patchWorkout],
  )

  const finish = useCallback(
    (workoutCid: string, body: { intensity: Intensity; duration_min: number; notes?: string; kcal: number }) => {
      const ended = new Date().toISOString()
      patchWorkout(workoutCid, (w) => ({ ...w, ended_at: ended, duration_min: body.duration_min, intensity: body.intensity, notes: body.notes ?? w.notes, kcal: body.kcal }))
      void enqueue({
        type: 'workout.patch',
        clientId: workoutCid,
        body: { ended_at: ended, duration_min: body.duration_min, intensity: body.intensity, ...(body.notes !== undefined ? { notes: body.notes } : {}) },
      })
    },
    [patchWorkout],
  )

  const rename = useCallback(
    (workoutCid: string, name: string) => {
      patchWorkout(workoutCid, (w) => ({ ...w, name }))
      void enqueue({ type: 'workout.patch', clientId: workoutCid, body: { name } })
    },
    [patchWorkout],
  )

  const removeWorkout = useCallback(
    (workoutCid: string) => {
      update((data) => ({ ...data, workouts: data.workouts.filter((w) => w.client_id !== workoutCid) }))
      void enqueue({ type: 'workout.delete', clientId: workoutCid })
    },
    [update],
  )

  const createExercise = useCallback(
    (name: string, muscle: Muscle, unit: ExerciseUnit): Exercise => {
      const exercise: Exercise = { client_id: newClientId(), name: name.trim(), muscle, unit, custom: true, archived: false }
      update((data) => ({ ...data, exercises: [...data.exercises, exercise] }))
      void enqueue({ type: 'exercise.create', body: { client_id: exercise.client_id, name: exercise.name, muscle, unit } })
      return exercise
    },
    [update],
  )

  const saveTemplate = useCallback(
    (template: { client_id?: string; name: string; exercises: TemplateExercise[] }) => {
      const cid = template.client_id ?? newClientId()
      update((data) => {
        const exists = data.templates.some((t) => t.client_id === cid)
        const next = { client_id: cid, name: template.name, exercises: template.exercises, position: data.templates.length }
        return { ...data, templates: exists ? data.templates.map((t) => (t.client_id === cid ? { ...t, ...next, position: t.position } : t)) : [...data.templates, next] }
      })
      void enqueue({ type: 'template.save', body: { client_id: cid, name: template.name, exercises: template.exercises } })
      return cid
    },
    [update],
  )

  const removeTemplate = useCallback(
    (cid: string) => {
      update((data) => ({ ...data, templates: data.templates.filter((t) => t.client_id !== cid) }))
      void enqueue({ type: 'template.delete', clientId: cid })
    },
    [update],
  )

  return { start, addSet, updateSet, removeSet, finish, rename, removeWorkout, createExercise, saveTemplate, removeTemplate }
}

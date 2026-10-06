import clsx from 'clsx'
import { motion } from 'motion/react'
import { Check, Copy, Minus, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useApp, usePrefsActions } from '@/hooks/data'
import { useTrainingActions } from '@/hooks/training'
import { fmtShort } from '@/lib/dates'
import { fmt } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import {
  fmtElapsed,
  fmtSet,
  MUSCLE_LABEL,
  nextSet,
  sessionExercises,
  UNIT_LABEL,
  type Exercise,
  type LastPerformance,
  type TemplateExercise,
  type TrainingData,
  type WorkoutSession,
  type WorkoutSetRow,
} from '@/lib/training'
import { Button } from '@/ui/Button'
import { NumberInput } from '@/ui/Field'
import { toast } from '@/ui/toast'
import { ExercisePicker } from './ExercisePicker'
import { FinishSheet } from './FinishSheet'
import { RestTimer } from './RestTimer'

const EXTRA_KEY = (cid: string) => `kcalia:entreno:${cid}:extra`

function readExtra(cid: string): string[] {
  try {
    return JSON.parse(localStorage.getItem(EXTRA_KEY(cid)) ?? '[]') as string[]
  } catch {
    return []
  }
}

function Big({ label, value, onChange, step, min, max, suffix, decimals }: { label: string; value: number; onChange: (v: number) => void; step: number; min: number; max: number; suffix: string; decimals: number }) {
  const set = (next: number) => {
    const clamped = Math.min(max, Math.max(min, Math.round(next * 100) / 100))
    if (clamped !== value) {
      haptic('select')
      onChange(clamped)
    }
  }
  return (
    <div role="group" aria-label={label} className="flex min-w-0 flex-1 items-center gap-1 rounded-md border border-border bg-surface-2 p-1">
      <button type="button" onClick={() => set(value - step)} aria-label={`${label}: menos`} className="grid size-12 shrink-0 place-items-center rounded-sm bg-surface text-text active:scale-95">
        <Minus className="size-5" aria-hidden />
      </button>
      <span className="flex min-w-0 flex-1 flex-col items-center">
        <NumberInput value={value} onChange={(v) => v !== null && set(v)} decimals={decimals} min={min} max={max} ariaLabel={label} className="w-full text-center text-[22px] leading-tight font-semibold text-text" />
        <span className="text-[11.5px] text-text-3">{suffix}</span>
      </span>
      <button type="button" onClick={() => set(value + step)} aria-label={`${label}: más`} className="grid size-12 shrink-0 place-items-center rounded-sm bg-surface text-text active:scale-95">
        <Plus className="size-5" aria-hidden />
      </button>
    </div>
  )
}

interface CardProps {
  exercise: Exercise
  sets: WorkoutSetRow[]
  plan: TemplateExercise | null
  last: LastPerformance | undefined
  focused: boolean
  onFocus: () => void
  onAdd: (weight: number, reps: number) => void
  onUpdate: (set: WorkoutSetRow, body: { weight?: number; reps?: number }) => void
  onRemove: (set: WorkoutSetRow) => void
}

function ExerciseCard({ exercise, sets, plan, last, focused, onFocus, onAdd, onUpdate, onRemove }: CardProps) {
  const proposal = nextSet(sets[sets.length - 1], last, plan)
  const [weight, setWeight] = useState(proposal.weight)
  const [reps, setReps] = useState(proposal.reps)
  const counted = exercise.unit === 'reps'
  const done = plan ? sets.length >= plan.sets : false

  // Al guardar una serie, la siguiente propuesta parte de ella.
  useEffect(() => {
    setWeight(proposal.weight)
    setReps(proposal.reps)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sets.length])

  return (
    <section className={clsx('card p-4', focused && 'border-accent')} aria-label={exercise.name}>
      <button type="button" onClick={onFocus} className="flex w-full items-start justify-between gap-3 text-left">
        <span className="min-w-0">
          <span className="flex items-center gap-2 text-[16px] font-semibold text-text">
            {done && <Check className="size-4 text-accent-text" aria-label="Series previstas hechas" />}
            {exercise.name}
          </span>
          <span className="mt-0.5 block text-[12.5px] text-text-3" data-num>
            {MUSCLE_LABEL[exercise.muscle]}
            {plan && ` · plan ${plan.sets} × ${plan.reps}`}
            {last && ` · última vez ${fmtSet(last.weight, last.reps, exercise.unit)} (${fmtShort(last.date)})`}
          </span>
        </span>
        <span className="shrink-0 text-[13px] font-medium text-text-2" data-num>
          {sets.length}
          {plan ? `/${plan.sets}` : ''} series
        </span>
      </button>

      {sets.length > 0 && (
        <ol className="mt-3 divide-y divide-border rounded-md border border-border">
          {sets.map((set, index) => (
            <li key={set.client_id} className="flex items-center gap-2 py-1 pr-1 pl-3">
              <span className="w-5 text-[13px] font-semibold text-text-3" data-num>
                {index + 1}
              </span>
              {counted && (
                <label className="flex h-10 items-center gap-1 rounded-sm bg-surface-2 px-2">
                  <NumberInput value={set.weight} onChange={(v) => v !== null && onUpdate(set, { weight: v })} decimals={2} min={0} max={1000} ariaLabel={`Peso de la serie ${index + 1}`} className="w-[5ch] text-right text-[15px] text-text" />
                  <span className="text-[12px] text-text-3">kg</span>
                </label>
              )}
              <label className="flex h-10 items-center gap-1 rounded-sm bg-surface-2 px-2">
                <NumberInput value={set.reps} onChange={(v) => v !== null && onUpdate(set, { reps: Math.round(v) })} decimals={0} min={0} max={600} ariaLabel={`${UNIT_LABEL[exercise.unit]} de la serie ${index + 1}`} className="w-[3.5ch] text-right text-[15px] text-text" />
                <span className="text-[12px] text-text-3">{UNIT_LABEL[exercise.unit]}</span>
              </label>
              <span className="flex-1" />
              <button type="button" onClick={() => onRemove(set)} aria-label={`Borrar la serie ${index + 1}`} className="grid size-10 place-items-center rounded-full text-text-3 hover:text-danger-text">
                <Trash2 className="size-4" aria-hidden />
              </button>
            </li>
          ))}
        </ol>
      )}

      {focused ? (
        <div className="mt-3 space-y-2.5">
          <div className="flex gap-2">
            {counted && <Big label="Peso" value={weight} onChange={setWeight} step={2.5} min={0} max={1000} suffix="kg" decimals={2} />}
            <Big
              label={exercise.unit === 'reps' ? 'Repeticiones' : exercise.unit === 'seg' ? 'Segundos' : 'Minutos'}
              value={reps}
              onChange={(v) => setReps(Math.round(v))}
              step={exercise.unit === 'seg' ? 5 : 1}
              min={0}
              max={600}
              suffix={UNIT_LABEL[exercise.unit]}
              decimals={0}
            />
          </div>
          <div className="flex gap-2">
            {sets.length > 0 && (
              <Button variant="secondary" size="lg" className="flex-1" onClick={() => onAdd(sets[sets.length - 1].weight, sets[sets.length - 1].reps)} icon={<Copy className="size-5" aria-hidden />}>
                Repetir
              </Button>
            )}
            <Button size="lg" className="flex-[1.6]" disabled={reps <= 0} onClick={() => onAdd(weight, reps)} icon={<Check className="size-5" strokeWidth={2.6} aria-hidden />}>
              Serie {sets.length + 1}
            </Button>
          </div>
        </div>
      ) : (
        <Button variant="ghost" size="sm" block className="mt-2" onClick={onFocus}>
          Registrar serie
        </Button>
      )}
    </section>
  )
}

/** Sesión en curso: ejercicios, series con referencia de la última vez, descanso y terminar. */
export function ActiveWorkout({ session, data }: { session: WorkoutSession; data: TrainingData }) {
  const app = useApp()
  const actions = useTrainingActions()
  const savePrefs = usePrefsActions()
  const restSeconds = app.prefs?.rest_seconds ?? 90
  const [extra, setExtra] = useState<string[]>(() => readExtra(session.client_id))
  const [picking, setPicking] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const [restEndsAt, setRestEndsAt] = useState<number | null>(null)
  const [now, setNow] = useState(Date.now())
  const template = data.templates.find((t) => t.client_id === session.template_cid)
  const items = useMemo(() => sessionExercises(session, template, extra), [session, template, extra])
  const byCid = useMemo(() => new Map(data.exercises.map((e) => [e.client_id, e])), [data.exercises])
  const firstPending = items.find((i) => (i.plan ? i.sets.length < i.plan.sets : i.sets.length === 0))?.exercise ?? items[0]?.exercise ?? null
  const [focus, setFocus] = useState<string | null>(firstPending)

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(EXTRA_KEY(session.client_id), JSON.stringify(extra))
    } catch {
      // Sin almacenamiento, la lista de ejercicios añadidos dura lo que la pantalla.
    }
  }, [extra, session.client_id])

  function addSet(exercise: string, weight: number, reps: number) {
    actions.addSet(session.client_id, exercise, weight, reps)
    haptic('success')
    setRestEndsAt(Date.now() + restSeconds * 1000)
  }

  return (
    <div className="mt-4 space-y-3 pb-24">
      <div className="card flex items-center justify-between gap-3 p-4">
        <div className="min-w-0">
          <label className="sr-only" htmlFor="workout-name">
            Nombre del entreno
          </label>
          <input
            id="workout-name"
            defaultValue={session.name}
            maxLength={60}
            onBlur={(event) => event.target.value.trim() && event.target.value.trim() !== session.name && actions.rename(session.client_id, event.target.value.trim())}
            className="w-full rounded-sm bg-transparent text-[19px] font-semibold tracking-[-0.02em] text-text outline-none focus:bg-surface-2 focus:px-2"
          />
          <p className="mt-0.5 text-[13px] text-text-3" data-num>
            {fmtElapsed(now - Date.parse(session.started_at))} · {session.sets.length} series · {fmt(session.volume)} kg de volumen
          </p>
        </div>
        <Button size="sm" onClick={() => setFinishing(true)}>
          Terminar
        </Button>
      </div>

      {items.map((item) => {
        const exercise = byCid.get(item.exercise)
        if (!exercise) return null
        return (
          <motion.div key={item.exercise} layout="position">
            <ExerciseCard
              exercise={exercise}
              sets={item.sets}
              plan={item.plan}
              last={data.last[item.exercise]}
              focused={focus === item.exercise}
              onFocus={() => setFocus(item.exercise)}
              onAdd={(weight, reps) => addSet(item.exercise, weight, reps)}
              onUpdate={(set, body) => actions.updateSet(session.client_id, set.client_id, body)}
              onRemove={(set) => {
                actions.removeSet(session.client_id, set.client_id)
                toast({ title: 'Serie borrada', action: { label: 'Deshacer', onClick: () => actions.addSet(session.client_id, set.exercise, set.weight, set.reps, set.rpe) } })
              }}
            />
          </motion.div>
        )
      })}

      <Button variant="secondary" size="lg" block onClick={() => setPicking(true)} icon={<Plus className="size-5" aria-hidden />}>
        Añadir ejercicio
      </Button>

      <ExercisePicker
        open={picking}
        exercises={data.exercises}
        taken={items.map((i) => i.exercise)}
        onClose={() => setPicking(false)}
        onCreate={(name, muscle, unit) => actions.createExercise(name, muscle, unit)}
        onPick={(exercise) => {
          setExtra((list) => [...list, exercise.client_id])
          setFocus(exercise.client_id)
          setPicking(false)
        }}
      />
      <FinishSheet open={finishing} session={session} onClose={() => setFinishing(false)} />
      <RestTimer
        endsAt={restEndsAt}
        seconds={restSeconds}
        onChange={setRestEndsAt}
        onSeconds={(seconds) => savePrefs({ rest_seconds: seconds })}
      />
    </div>
  )
}

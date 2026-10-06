import clsx from 'clsx'
import { Plus, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { haptic } from '@/lib/haptics'
import { normalize } from '@/lib/textnorm'
import { MUSCLE_LABEL, MUSCLES, type Exercise, type ExerciseUnit, type Muscle } from '@/lib/training'
import { Button } from '@/ui/Button'
import { Sheet } from '@/ui/Sheet'

interface Props {
  open: boolean
  exercises: Exercise[]
  /** Ya en la sesión: se marcan y no se repiten. */
  taken: string[]
  onClose: () => void
  onPick: (exercise: Exercise) => void
  onCreate: (name: string, muscle: Muscle, unit: ExerciseUnit) => Exercise
}

/** Buscar un ejercicio por nombre o grupo muscular, o crear uno propio (también sin conexión). */
export function ExercisePicker({ open, exercises, taken, onClose, onPick, onCreate }: Props) {
  const [query, setQuery] = useState('')
  const [muscle, setMuscle] = useState<Muscle | null>(null)
  const [creating, setCreating] = useState(false)
  const [newMuscle, setNewMuscle] = useState<Muscle>('otro')
  const [unit, setUnit] = useState<ExerciseUnit>('reps')

  const list = useMemo(() => {
    const words = normalize(query).split(' ').filter(Boolean)
    return exercises
      .filter((e) => !e.archived && (!muscle || e.muscle === muscle) && words.every((w) => normalize(e.name).includes(w)))
      .sort((a, b) => a.name.localeCompare(b.name, 'es'))
  }, [exercises, query, muscle])

  function pick(exercise: Exercise) {
    haptic('select')
    onPick(exercise)
    setQuery('')
    setCreating(false)
  }

  return (
    <Sheet open={open} onClose={onClose} title="Añadir ejercicio" tall>
      <div className="space-y-3">
        <label className="flex h-12 items-center gap-2.5 rounded-md border border-border bg-surface-2 px-3.5 focus-within:border-accent">
          <Search className="size-[18px] shrink-0 text-text-3" aria-hidden />
          <span className="sr-only">Buscar ejercicio</span>
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar: sentadilla, remo…" className="h-full min-w-0 flex-1 bg-transparent text-text outline-none placeholder:text-text-3" />
        </label>
        <div role="radiogroup" aria-label="Grupo muscular" className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5">
          {[{ key: null, label: 'Todos' } as { key: Muscle | null; label: string }, ...MUSCLES].map((m) => (
            <button
              key={m.key ?? 'todos'}
              type="button"
              role="radio"
              aria-checked={muscle === m.key}
              onClick={() => setMuscle(m.key)}
              className={clsx('h-10 shrink-0 rounded-full border px-3.5 text-[13.5px] font-medium', muscle === m.key ? 'border-accent bg-accent-soft text-accent-text' : 'border-border bg-surface-2 text-text-2')}
            >
              {m.label}
            </button>
          ))}
        </div>
        <ul className="card divide-y divide-border overflow-hidden">
          {list.map((exercise) => {
            const inSession = taken.includes(exercise.client_id)
            return (
              <li key={exercise.client_id}>
                <button type="button" disabled={inSession} onClick={() => pick(exercise)} className="flex min-h-[52px] w-full items-center gap-3 px-4 py-2 text-left hover:bg-surface-2 disabled:opacity-45">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px] text-text">{exercise.name}</span>
                    <span className="block text-[12.5px] text-text-3">{MUSCLE_LABEL[exercise.muscle]}{inSession ? ' · ya en la sesión' : ''}</span>
                  </span>
                  <Plus className="size-4 shrink-0 text-text-3" aria-hidden />
                </button>
              </li>
            )
          })}
          {list.length === 0 && <li className="px-4 py-6 text-center text-[14px] text-text-3">Ningún ejercicio coincide.</li>}
        </ul>
        {creating ? (
          <div className="space-y-3 rounded-md border border-border bg-surface p-3.5">
            <p className="text-[14px] font-semibold text-text">Nuevo ejercicio: «{query.trim() || '…'}»</p>
            <label className="block">
              <span className="mb-1 block text-[13px] text-text-2">Grupo muscular</span>
              <select value={newMuscle} onChange={(e) => setNewMuscle(e.target.value as Muscle)} className="h-12 w-full rounded-md border border-border bg-surface-2 px-3 text-text">
                {MUSCLES.map((m) => (
                  <option key={m.key} value={m.key}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[13px] text-text-2">Cada serie cuenta</span>
              <select value={unit} onChange={(e) => setUnit(e.target.value as ExerciseUnit)} className="h-12 w-full rounded-md border border-border bg-surface-2 px-3 text-text">
                <option value="reps">Repeticiones</option>
                <option value="seg">Segundos</option>
                <option value="min">Minutos</option>
              </select>
            </label>
            <Button block disabled={!query.trim()} onClick={() => pick(onCreate(query, newMuscle, unit))}>
              Crear y añadir
            </Button>
          </div>
        ) : (
          <Button variant="ghost" block onClick={() => setCreating(true)} icon={<Plus className="size-4" aria-hidden />}>
            {query.trim() ? `Crear «${query.trim()}»` : 'Crear un ejercicio propio'}
          </Button>
        )}
      </div>
    </Sheet>
  )
}

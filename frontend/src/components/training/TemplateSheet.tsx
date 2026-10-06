import { Minus, Plus, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTrainingActions } from '@/hooks/training'
import { haptic } from '@/lib/haptics'
import type { Exercise, TemplateExercise, WorkoutTemplate } from '@/lib/training'
import { Button } from '@/ui/Button'
import { Field } from '@/ui/Field'
import { Sheet } from '@/ui/Sheet'
import { toast } from '@/ui/toast'
import { ExercisePicker } from './ExercisePicker'

function Count({ label, value, onChange, max }: { label: string; value: number; onChange: (v: number) => void; max: number }) {
  return (
    <span role="group" aria-label={label} className="flex items-center gap-1">
      <button type="button" onClick={() => onChange(Math.max(1, value - 1))} aria-label={`${label}: menos`} className="grid size-9 place-items-center rounded-full border border-border bg-surface-2 text-text">
        <Minus className="size-3.5" aria-hidden />
      </button>
      <span className="w-7 text-center text-[15px] font-semibold text-text" data-num>
        {value}
      </span>
      <button type="button" onClick={() => onChange(Math.min(max, value + 1))} aria-label={`${label}: más`} className="grid size-9 place-items-center rounded-full border border-border bg-surface-2 text-text">
        <Plus className="size-3.5" aria-hidden />
      </button>
    </span>
  )
}

/** Crear o editar una plantilla de rutina: nombre y ejercicios con series × repeticiones. */
export function TemplateSheet({ template, open, exercises, onClose }: { template: WorkoutTemplate | null; open: boolean; exercises: Exercise[]; onClose: () => void }) {
  const actions = useTrainingActions()
  const [name, setName] = useState('')
  const [items, setItems] = useState<TemplateExercise[]>([])
  const [picking, setPicking] = useState(false)
  const byCid = new Map(exercises.map((e) => [e.client_id, e]))

  useEffect(() => {
    if (!open) return
    setName(template?.name ?? '')
    setItems(template?.exercises ?? [])
  }, [open, template])

  function save() {
    actions.saveTemplate({ client_id: template?.client_id, name: name.trim(), exercises: items })
    haptic('success')
    toast.success(template ? 'Plantilla guardada' : 'Plantilla creada', name.trim())
    onClose()
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={template ? 'Editar plantilla' : 'Nueva plantilla'}
      tall
      footer={
        <Button size="lg" block disabled={!name.trim()} onClick={save}>
          Guardar plantilla
        </Button>
      }
    >
      <div className="space-y-4">
        <Field label="Nombre" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} placeholder="Por ejemplo: Torso" />
        <ul className="card divide-y divide-border overflow-hidden">
          {items.map((item, index) => (
            <li key={`${item.exercise}-${index}`} className="flex items-center gap-2 px-3.5 py-2">
              <span className="min-w-0 flex-1 truncate text-[14.5px] text-text">{byCid.get(item.exercise)?.name ?? 'Ejercicio'}</span>
              <Count label="Series" value={item.sets} max={20} onChange={(sets) => setItems((list) => list.map((it, i) => (i === index ? { ...it, sets } : it)))} />
              <X className="size-3 text-text-3" aria-hidden />
              <Count label="Repeticiones" value={item.reps} max={600} onChange={(reps) => setItems((list) => list.map((it, i) => (i === index ? { ...it, reps } : it)))} />
              <button type="button" onClick={() => setItems((list) => list.filter((_, i) => i !== index))} aria-label="Quitar de la plantilla" className="grid size-10 place-items-center rounded-full text-text-3 hover:text-danger-text">
                <Trash2 className="size-4" aria-hidden />
              </button>
            </li>
          ))}
          {items.length === 0 && <li className="px-4 py-6 text-center text-[14px] text-text-3">Añade los ejercicios de esta rutina.</li>}
        </ul>
        <Button variant="secondary" block onClick={() => setPicking(true)} icon={<Plus className="size-4" aria-hidden />}>
          Añadir ejercicio
        </Button>
        {template && (
          <Button
            variant="danger"
            size="sm"
            onClick={() => {
              actions.removeTemplate(template.client_id)
              toast({ title: 'Plantilla borrada', description: template.name })
              onClose()
            }}
            icon={<Trash2 className="size-4" aria-hidden />}
          >
            Borrar plantilla
          </Button>
        )}
      </div>
      <ExercisePicker
        open={picking}
        exercises={exercises}
        taken={items.map((i) => i.exercise)}
        onClose={() => setPicking(false)}
        onCreate={(n, muscle, unit) => actions.createExercise(n, muscle, unit)}
        onPick={(exercise) => {
          setItems((list) => [...list, { exercise: exercise.client_id, sets: 3, reps: exercise.unit === 'seg' ? 30 : 10 }])
          setPicking(false)
        }}
      />
    </Sheet>
  )
}

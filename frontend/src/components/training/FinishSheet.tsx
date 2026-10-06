import { useQueryClient } from '@tanstack/react-query'
import { Flame } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useApp } from '@/hooks/data'
import { useTrainingActions } from '@/hooks/training'
import { fmt } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { estimatedKcal, type Intensity, type WorkoutSession } from '@/lib/training'
import type { Bootstrap } from '@/lib/types'
import { keys } from '@/offline/queryClient'
import { Button } from '@/ui/Button'
import { Stepper } from '@/ui/Field'
import { Segmented } from '@/ui/Segmented'
import { Sheet } from '@/ui/Sheet'
import { toast } from '@/ui/toast'

/** Terminar la sesión: duración, intensidad y calorías estimadas (orientativas). */
export function FinishSheet({ open, session, onClose }: { open: boolean; session: WorkoutSession; onClose: () => void }) {
  const app = useApp()
  const client = useQueryClient()
  const actions = useTrainingActions()
  const elapsed = Math.max(1, Math.round((Date.now() - Date.parse(session.started_at)) / 60_000))
  const [minutes, setMinutes] = useState(elapsed)
  const [intensity, setIntensity] = useState<Intensity>('moderada')
  const [notes, setNotes] = useState(session.notes)
  const adds = !!app.prefs?.add_exercise_kcal

  useEffect(() => {
    if (open) setMinutes(Math.min(600, Math.max(1, Math.round((Date.now() - Date.parse(session.started_at)) / 60_000))))
  }, [open, session.started_at])

  const kcal = estimatedKcal(minutes, intensity, app.profile.weight_kg)

  function save() {
    actions.finish(session.client_id, { intensity, duration_min: minutes, notes, kcal })
    // El objetivo del día (si se suman las calorías del entreno) se recalcula en el móvil al momento.
    client.setQueryData<Bootstrap>(keys.bootstrap, (old) =>
      old ? { ...old, exercise_kcal: { ...(old.exercise_kcal ?? {}), [session.date]: (old.exercise_kcal?.[session.date] ?? 0) + kcal } } : old,
    )
    haptic('success')
    toast.success('Entreno guardado', `${session.sets.length} series · ≈ ${fmt(kcal)} kcal`)
    onClose()
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Terminar entreno"
      footer={
        <Button size="lg" block onClick={save}>
          Guardar entreno
        </Button>
      }
    >
      <div className="space-y-5">
        <Stepper label="Duración" value={minutes} onChange={setMinutes} step={5} min={1} max={600} unit="min" />
        <div>
          <span className="eyebrow">Intensidad</span>
          <Segmented
            className="mt-2"
            label="Intensidad"
            value={intensity}
            onChange={setIntensity}
            options={[
              { value: 'suave', label: 'Suave' },
              { value: 'moderada', label: 'Moderada' },
              { value: 'intensa', label: 'Intensa' },
            ]}
          />
        </div>
        <div className="flex items-start gap-3 rounded-md bg-surface-2 p-3.5">
          <Flame className="mt-0.5 size-5 shrink-0 text-kcal-from" aria-hidden />
          <p className="text-[14px] leading-relaxed text-text-2" data-num>
            <strong className="font-semibold text-text">≈ {fmt(kcal)} kcal</strong> con {fmt(app.profile.weight_kg, 1)} kg y {minutes} min.{' '}
            {adds ? 'Se suman a tu objetivo de hoy en forma de hidratos.' : 'Solo como referencia: puedes sumarlas al objetivo en Ajustes.'} Es una estimación, no una medida.
          </p>
        </div>
        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-text-2">Notas (opcional)</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={1000} className="block w-full resize-none rounded-md border border-border bg-surface-2 px-3.5 py-2.5 text-text outline-none focus:border-accent" />
        </label>
      </div>
    </Sheet>
  )
}

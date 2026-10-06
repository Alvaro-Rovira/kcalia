import { Dumbbell, Pencil, Play, Plus, Trash2, TrendingUp } from 'lucide-react'
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import { ActiveWorkout } from '@/components/training/ActiveWorkout'
import { TemplateSheet } from '@/components/training/TemplateSheet'
import { useExerciseHistory, useTraining, useTrainingActions } from '@/hooks/training'
import { capitalize, fmt, plural } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { relativeDay } from '@/lib/dates'
import { activeWorkout, fmtSet, sessionExercises, type WorkoutSession, type WorkoutTemplate } from '@/lib/training'
import { Button } from '@/ui/Button'
import { EmptyState } from '@/ui/EmptyState'
import { Sheet } from '@/ui/Sheet'
import { Skeleton } from '@/ui/Skeleton'
import { toast } from '@/ui/toast'

const TrendChart = lazy(() => import('@/components/charts/TrendChart'))

export default function Workout() {
  const training = useTraining()
  const actions = useTrainingActions()
  const [params, setParams] = useSearchParams()
  const [editing, setEditing] = useState<WorkoutTemplate | null | 'new'>(null)
  const [detail, setDetail] = useState<WorkoutSession | null>(null)
  const [progress, setProgress] = useState<string | null>(null)
  const data = training.data
  const active = data ? activeWorkout(data.workouts) : null
  const byCid = useMemo(() => new Map((data?.exercises ?? []).map((e) => [e.client_id, e])), [data?.exercises])
  const trained = useMemo(() => Object.keys(data?.last ?? {}).filter((cid) => byCid.has(cid) && byCid.get(cid)!.unit === 'reps'), [data?.last, byCid])
  const history = useExerciseHistory(progress ?? trained[0] ?? null)

  // Atajo de la PWA instalada: /entreno?nuevo=1 empieza un entreno libre (si no hay uno en marcha).
  useEffect(() => {
    if (params.get('nuevo') !== '1' || !data) return
    setParams({}, { replace: true })
    if (!active) actions.start('Entreno')
  }, [params, data, active, actions, setParams])

  function start(name: string, template: string | null = null) {
    haptic('success')
    actions.start(name, template)
  }

  return (
    <main className="page">
      <header>
        <h1 className="text-[30px] leading-tight font-semibold tracking-[-0.035em] text-text">Entreno</h1>
        <p className="mt-1 text-[14.5px] text-text-2">{active ? 'En marcha. Apunta cada serie al terminarla.' : 'Tus rutinas, tus series y cómo progresas.'}</p>
      </header>

      {training.isPending ? (
        <div className="mt-4 space-y-3" role="status" aria-label="Cargando entrenos">
          <Skeleton className="h-14" />
          <Skeleton className="h-40 !rounded-[22px]" />
        </div>
      ) : !data ? (
        <div className="card mt-4">
          <EmptyState art="offline" title="Sin datos de entreno" text="Conéctate una vez para descargar tus ejercicios y rutinas." compact />
        </div>
      ) : active ? (
        <ActiveWorkout session={active} data={data} />
      ) : (
        <>
          <Button size="lg" block className="mt-4" onClick={() => start('Entreno')} icon={<Play className="size-5" aria-hidden />}>
            Empezar entreno libre
          </Button>

          <section className="mt-7" aria-labelledby="t-templates">
            <div className="flex items-baseline justify-between gap-3 px-1">
              <h2 id="t-templates" className="text-[17px] font-semibold text-text">
                Rutinas
              </h2>
              <button type="button" onClick={() => setEditing('new')} className="inline-flex min-h-11 items-center gap-1 text-[14px] font-medium text-accent-text">
                <Plus className="size-4" aria-hidden /> Nueva
              </button>
            </div>
            <ul className="mt-2 grid gap-2.5 sm:grid-cols-2">
              {data.templates.map((template) => (
                <li key={template.client_id} className="card flex items-center gap-3 p-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-[16px] font-semibold text-text">{template.name}</p>
                    <p className="mt-0.5 line-clamp-2 text-[13px] text-text-3">
                      {template.exercises.map((e) => byCid.get(e.exercise)?.name).filter(Boolean).join(' · ') || 'Sin ejercicios'}
                    </p>
                  </div>
                  <button type="button" onClick={() => setEditing(template)} aria-label={`Editar ${template.name}`} className="grid size-11 shrink-0 place-items-center rounded-full text-text-3 hover:bg-surface-2">
                    <Pencil className="size-4" aria-hidden />
                  </button>
                  <Button size="sm" onClick={() => start(template.name, template.client_id)} aria-label={`Empezar ${template.name}`}>
                    Empezar
                  </Button>
                </li>
              ))}
            </ul>
          </section>

          <section className="mt-7" aria-labelledby="t-recent">
            <h2 id="t-recent" className="px-1 text-[17px] font-semibold text-text">
              Últimos entrenos
            </h2>
            {data.workouts.length === 0 ? (
              <p className="card mt-2 px-4 py-5 text-[14.5px] text-text-2">Cuando termines tu primer entreno aparecerá aquí, con su volumen y su duración.</p>
            ) : (
              <ul className="card mt-2 divide-y divide-border overflow-hidden">
                {data.workouts.slice(0, 12).map((w) => (
                  <li key={w.client_id}>
                    <button type="button" onClick={() => setDetail(w)} className="flex min-h-[60px] w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-surface-2">
                      <Dumbbell className="size-[18px] shrink-0 text-text-3" aria-hidden />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[15px] font-medium text-text">{w.name}</span>
                        <span className="block text-[12.5px] text-text-3" data-num>
                          {capitalize(relativeDay(w.date))} · {w.sets.length} {plural(w.sets.length, 'serie', 'series')}
                          {w.duration_min ? ` · ${w.duration_min} min` : ''}
                          {w.kcal ? ` · ≈ ${fmt(w.kcal)} kcal` : ''}
                        </span>
                      </span>
                      <span className="shrink-0 text-[14px] font-semibold text-text" data-num>
                        {fmt(w.volume)} <span className="text-[12px] font-medium text-text-3">kg</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {trained.length > 0 && (
            <section className="card mt-7 p-4" aria-labelledby="t-progress">
              <h2 id="t-progress" className="flex items-center gap-2 text-[17px] font-semibold text-text">
                <TrendingUp className="size-[18px] text-accent-text" aria-hidden /> Progresión
              </h2>
              <label className="mt-3 block">
                <span className="sr-only">Ejercicio</span>
                <select value={progress ?? trained[0]} onChange={(e) => setProgress(e.target.value)} className="h-12 w-full rounded-md border border-border bg-surface-2 px-3 text-text">
                  {trained.map((cid) => (
                    <option key={cid} value={cid}>
                      {byCid.get(cid)?.name}
                    </option>
                  ))}
                </select>
              </label>
              {history.data && history.data.sessions.length > 0 ? (
                <>
                  <p className="mt-3 text-[13px] text-text-2">1RM estimado (fórmula de Epley) de la mejor serie de cada sesión.</p>
                  <div className="mt-2">
                    <Suspense fallback={<Skeleton className="h-[200px]" />}>
                      <TrendChart points={history.data.sessions.map((s) => ({ date: s.date, value: s.best_1rm }))} label="1RM estimado" unit="kg" />
                    </Suspense>
                  </div>
                  <ul className="mt-3 space-y-1 text-[13px] text-text-2" data-num>
                    {[...history.data.sessions]
                      .reverse()
                      .slice(0, 5)
                      .map((s) => (
                        <li key={s.date} className="flex justify-between gap-3">
                          <span>{capitalize(relativeDay(s.date))}</span>
                          <span>
                            {fmtSet(s.top_weight, s.top_reps)} · volumen {fmt(s.volume)} kg
                          </span>
                        </li>
                      ))}
                  </ul>
                </>
              ) : (
                <p className="mt-3 text-[13.5px] text-text-3">{history.isPending ? 'Cargando…' : 'Sin datos todavía para este ejercicio.'}</p>
              )}
            </section>
          )}
        </>
      )}

      <TemplateSheet open={editing !== null} template={editing === 'new' ? null : editing} exercises={data?.exercises ?? []} onClose={() => setEditing(null)} />
      <Sheet open={!!detail} onClose={() => setDetail(null)} title={detail?.name ?? 'Entreno'}>
        {detail && data && (
          <div className="space-y-4">
            <p className="text-[13.5px] text-text-2" data-num>
              {capitalize(relativeDay(detail.date))}
              {detail.duration_min ? ` · ${detail.duration_min} min · intensidad ${detail.intensity}` : ''}
              {detail.kcal ? ` · ≈ ${fmt(detail.kcal)} kcal` : ''}
            </p>
            {sessionExercises(detail, undefined).map((item) => (
              <div key={item.exercise}>
                <p className="text-[15px] font-semibold text-text">{byCid.get(item.exercise)?.name ?? 'Ejercicio'}</p>
                <p className="mt-0.5 text-[13.5px] text-text-2" data-num>
                  {item.sets.map((s) => fmtSet(s.weight, s.reps, byCid.get(item.exercise)?.unit)).join(' · ')}
                </p>
              </div>
            ))}
            {detail.notes && <p className="rounded-md bg-surface-2 p-3 text-[14px] text-text-2">{detail.notes}</p>}
            <Button
              variant="danger"
              size="sm"
              onClick={() => {
                actions.removeWorkout(detail.client_id)
                toast({ title: 'Entreno borrado', description: detail.name })
                setDetail(null)
              }}
              icon={<Trash2 className="size-4" aria-hidden />}
            >
              Borrar entreno
            </Button>
          </div>
        )}
      </Sheet>
    </main>
  )
}

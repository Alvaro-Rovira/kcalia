import clsx from 'clsx'
import { Plus, Ruler, Trash2 } from 'lucide-react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { useMeasureActions, useMeasurements } from '@/hooks/data'
import { fmtMedium, relativeDay, todayISO } from '@/lib/dates'
import { capitalize, fmt, fmtSigned } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { EMPTY_MEASUREMENT, lastKnown, MEASURES, measureSeries } from '@/lib/measures'
import type { MeasureKey, Measurement } from '@/lib/types'
import { Button } from '@/ui/Button'
import { EmptyState } from '@/ui/EmptyState'
import { NumberInput } from '@/ui/Field'
import { Sheet } from '@/ui/Sheet'
import { Skeleton } from '@/ui/Skeleton'
import { toast } from '@/ui/toast'

const TrendChart = lazy(() => import('@/components/charts/TrendChart'))

/** Medidas corporales: apuntar las de un día, ver la evolución de cada una y el historial. */
export function MeasurementsPanel() {
  const measurements = useMeasurements()
  const actions = useMeasureActions()
  const [measure, setMeasure] = useState<MeasureKey>('waist')
  const [draft, setDraft] = useState<Measurement | null>(null)
  const entries = useMemo(() => measurements.data ?? [], [measurements.data])
  const series = measureSeries(entries, measure)
  const meta = MEASURES.find((m) => m.key === measure)!

  function open(date = todayISO()) {
    const existing = entries.find((e) => e.date === date)
    setDraft(existing ?? { ...EMPTY_MEASUREMENT(date), ...lastKnown(entries) })
  }

  function save() {
    if (!draft) return
    actions.save(draft)
    haptic('success')
    toast.success('Medidas guardadas', capitalize(relativeDay(draft.date)))
    setDraft(null)
  }

  function remove(entry: Measurement) {
    actions.remove(entry.date)
    toast({ title: 'Medidas borradas', description: capitalize(relativeDay(entry.date)), action: { label: 'Deshacer', onClick: () => actions.save(entry) } })
  }

  if (measurements.isPending) return <Skeleton className="mt-4 h-64 !rounded-[22px]" />

  return (
    <div className="mt-4 space-y-4">
      <Button block onClick={() => open()} icon={<Plus className="size-5" aria-hidden />}>
        Apuntar medidas
      </Button>

      {entries.length === 0 ? (
        <div className="card">
          <EmptyState
            art="scale"
            title="Aún no hay medidas"
            text="La cintura suele bajar antes que la báscula. Mídete cada dos o tres semanas, por la mañana y siempre igual."
            compact
          />
        </div>
      ) : (
        <>
          <section className="card p-4" aria-label={`Evolución de ${meta.label.toLowerCase()}`}>
            <div role="radiogroup" aria-label="Medida" className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
              {MEASURES.map((m) => (
                <button
                  key={m.key}
                  type="button"
                  role="radio"
                  aria-checked={measure === m.key}
                  onClick={() => {
                    haptic('select')
                    setMeasure(m.key)
                  }}
                  className={clsx(
                    'flex h-10 shrink-0 items-center rounded-full border px-3.5 text-[14px] font-medium transition-colors',
                    measure === m.key ? 'border-accent bg-accent-soft text-accent-text' : 'border-border bg-surface-2 text-text-2',
                  )}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <div className="mt-4 flex items-baseline justify-between gap-3">
              <p className="text-[30px] leading-none font-semibold tracking-[-0.03em] text-text" data-num>
                {series.latest ? fmt(series.latest.value, 1) : '—'} <span className="text-[15px] font-medium text-text-3">cm</span>
              </p>
              {series.change !== null && (
                <p className={clsx('text-[14px] font-semibold', series.change < 0 ? 'text-accent-text' : 'text-text-2')} data-num>
                  {fmtSigned(series.change, 1)} cm desde el {fmtMedium(series.points[0].date)}
                </p>
              )}
            </div>
            <div className="mt-3">
              {series.points.length ? (
                <Suspense fallback={<Skeleton className="h-[200px]" />}>
                  <TrendChart points={series.points} label={meta.label} unit="cm" />
                </Suspense>
              ) : (
                <p className="py-8 text-center text-[14px] text-text-3">Todavía no has apuntado la medida de {meta.label.toLowerCase()}.</p>
              )}
            </div>
          </section>

          <section aria-label="Historial de medidas">
            <ul className="card divide-y divide-border overflow-hidden">
              {[...entries].reverse().map((entry) => (
                <li key={entry.date} className="flex items-center gap-2 py-1.5 pr-1.5 pl-4">
                  <button type="button" onClick={() => open(entry.date)} className="min-w-0 flex-1 py-1.5 text-left">
                    <p className="text-[14.5px] font-medium text-text">{capitalize(relativeDay(entry.date))}</p>
                    <p className="mt-0.5 truncate text-[12.5px] text-text-3" data-num>
                      {MEASURES.filter((m) => entry[m.key] !== null)
                        .map((m) => `${m.label} ${fmt(entry[m.key] as number, 1)}`)
                        .join(' · ')}
                    </p>
                  </button>
                  <button type="button" onClick={() => remove(entry)} aria-label={`Borrar las medidas de ${relativeDay(entry.date).toLowerCase()}`} className="grid size-11 shrink-0 place-items-center rounded-full text-text-3 hover:text-danger-text">
                    <Trash2 className="size-4" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}

      <Sheet open={!!draft} onClose={() => setDraft(null)} title="Medidas" footer={<Button size="lg" block onClick={save}>Guardar medidas</Button>}>
        {draft && (
          <div className="space-y-4">
            <label className="flex min-h-11 items-center justify-between gap-3 text-[14px] text-text-2">
              <span>
                Del día <strong className="font-semibold text-text">{relativeDay(draft.date).toLowerCase()}</strong>
              </span>
              <input
                type="date"
                value={draft.date}
                max={todayISO()}
                onChange={(event) => event.target.value && setDraft((d) => (d ? { ...d, date: event.target.value } : d))}
                aria-label="Cambiar el día"
                className="h-11 rounded-sm border border-border bg-surface-2 px-2.5 text-[14px] text-text"
              />
            </label>
            <p className="flex items-center gap-2 text-[13px] text-text-3">
              <Ruler className="size-4 shrink-0" aria-hidden /> Con cinta métrica, en centímetros. Deja vacío lo que no midas.
            </p>
            {MEASURES.map((m) => (
              <label key={m.key} className="flex items-center gap-3">
                <span className="min-w-0 flex-1">
                  <span className="block text-[15px] text-text">{m.label}</span>
                  <span className="block text-[12.5px] text-text-3">{m.hint}</span>
                </span>
                <span className="flex h-12 w-[112px] items-center rounded-md border border-border bg-surface-2 px-3 focus-within:border-accent">
                  <NumberInput
                    value={draft[m.key]}
                    onChange={(value) => setDraft((d) => (d ? { ...d, [m.key]: value } : d))}
                    decimals={1}
                    min={10}
                    max={250}
                    ariaLabel={`${m.label} en centímetros`}
                    className="min-w-0 flex-1 text-[16px] text-text"
                  />
                  <span className="text-[13px] text-text-3">cm</span>
                </span>
              </label>
            ))}
          </div>
        )}
      </Sheet>
    </div>
  )
}

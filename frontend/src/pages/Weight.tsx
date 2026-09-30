import { useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { Plus, RefreshCw, Trash2, TrendingDown, TrendingUp } from 'lucide-react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { useApp, useOnline, useWeightActions, useWeights } from '@/hooks/data'
import { api, errorMessage } from '@/lib/api'
import { addDays, relativeDay, todayISO } from '@/lib/dates'
import { capitalize, fmt, fmtSigned, kgTo, toKg } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import type { WeightPoint } from '@/lib/types'
import { keys } from '@/offline/queryClient'
import { AnimatedNumber } from '@/ui/AnimatedNumber'
import { Button } from '@/ui/Button'
import { EmptyState } from '@/ui/EmptyState'
import { Stepper } from '@/ui/Field'
import { Segmented } from '@/ui/Segmented'
import { Sheet } from '@/ui/Sheet'
import { Skeleton } from '@/ui/Skeleton'
import { toast } from '@/ui/toast'

const WeightChart = lazy(() => import('@/components/charts/WeightChart'))

type Range = '30' | '90' | 'all'

export default function Weight() {
  const app = useApp()
  const unit = app.profile.weight_unit
  const weights = useWeights()
  const actions = useWeightActions()
  const client = useQueryClient()
  const online = useOnline()
  const today = todayISO()
  const [range, setRange] = useState<Range>('30')
  const [sheet, setSheet] = useState(false)
  const [draft, setDraft] = useState(kgTo(unit, app.profile.weight_kg))
  const [date, setDate] = useState(today)
  const [recalculating, setRecalculating] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  const entries = useMemo(() => weights.data?.entries ?? [], [weights.data])
  const visible = useMemo(() => {
    if (range === 'all') return entries
    const since = addDays(today, -Number(range))
    const filtered = entries.filter((e) => e.date >= since)
    return filtered.length ? filtered : entries.slice(-1)
  }, [entries, range, today])

  const latest = entries[entries.length - 1]
  const first = entries[0]
  const target = weights.data?.target_kg ?? null
  const convert = (kg: number) => kgTo(unit, kg)
  const totalChange = latest && first ? latest.avg - first.avg : 0
  const remaining = latest && target !== null ? target - latest.kg : null
  const recalc = dismissed ? null : weights.data?.recalc

  function openSheet() {
    setDraft(Number(convert(latest?.kg ?? app.profile.weight_kg).toFixed(1)))
    setDate(today)
    setSheet(true)
  }

  function save() {
    actions.save(date, Number(toKg(unit, draft).toFixed(2)))
    haptic('success')
    toast.success(`Peso guardado: ${fmt(draft, 1)} ${unit}`, date === today ? undefined : capitalize(relativeDay(date)))
    setSheet(false)
  }

  function remove(entry: WeightPoint) {
    actions.remove(entry.date)
    toast({
      title: 'Pesada borrada',
      description: `${fmt(convert(entry.kg), 1)} ${unit} · ${relativeDay(entry.date).toLowerCase()}`,
      action: { label: 'Deshacer', onClick: () => actions.save(entry.date, entry.kg) },
    })
  }

  async function recalculate() {
    setRecalculating(true)
    try {
      await api.post('/api/targets/recalculate')
      await Promise.all([client.invalidateQueries({ queryKey: keys.bootstrap }), client.invalidateQueries({ queryKey: keys.weight })])
      haptic('success')
      toast.success('Objetivos actualizados', 'Recalculados con tu peso actual.')
    } catch (error) {
      toast.error('No se han podido recalcular', errorMessage(error))
    } finally {
      setRecalculating(false)
    }
  }

  return (
    <main className="page">
      <header className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-[30px] leading-tight font-semibold tracking-[-0.035em] text-text">Peso</h1>
          <p className="mt-1 text-[14.5px] text-text-2">Fíjate en la media, no en el día.</p>
        </div>
        <Button size="sm" onClick={openSheet} icon={<Plus className="size-[18px]" aria-hidden />}>
          Apuntar
        </Button>
      </header>

      {weights.isPending ? (
        <div className="mt-4 space-y-4" role="status" aria-label="Cargando peso">
          <Skeleton className="h-[120px] !rounded-[22px]" />
          <Skeleton className="h-[300px] !rounded-[22px]" />
        </div>
      ) : entries.length === 0 ? (
        <div className="card mt-4">
          <EmptyState
            art="scale"
            title="Aún no hay pesadas"
            text="Pésate por la mañana, en ayunas. Con unas cuantas pesadas verás tu tendencia real."
            action={
              <Button onClick={openSheet} icon={<Plus className="size-5" aria-hidden />}>
                Apuntar peso
              </Button>
            }
          />
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <section className="card grid grid-cols-3 divide-x divide-border p-4" aria-label="Resumen de peso">
            <div className="pr-3">
              <p className="text-[12.5px] font-medium text-text-2">Media 7 días</p>
              <p className="mt-1 text-[26px] leading-none font-semibold tracking-[-0.03em] text-text">
                <AnimatedNumber value={convert(latest.avg)} decimals={1} from={convert(latest.avg)} />
                <span className="ml-1 text-[13px] font-medium text-text-3">{unit}</span>
              </p>
              <p className="mt-2 text-[12px] text-text-3" data-num>
                Última: {fmt(convert(latest.kg), 1)}
              </p>
            </div>
            <div className="px-3">
              <p className="text-[12.5px] font-medium text-text-2">Desde el inicio</p>
              <p className="mt-1 flex items-center gap-1 text-[26px] leading-none font-semibold tracking-[-0.03em] text-text" data-num>
                {fmtSigned(convert(totalChange), 1)}
                {Math.abs(totalChange) >= 0.05 &&
                  (totalChange < 0 ? <TrendingDown className="size-4 text-text-3" aria-hidden /> : <TrendingUp className="size-4 text-text-3" aria-hidden />)}
              </p>
              <p className="mt-2 text-[12px] text-text-3">
                {entries.length} {entries.length === 1 ? 'pesada' : 'pesadas'}
              </p>
            </div>
            <div className="pl-3">
              <p className="text-[12.5px] font-medium text-text-2">Objetivo</p>
              <p className="mt-1 text-[26px] leading-none font-semibold tracking-[-0.03em] text-text" data-num>
                {target === null ? '—' : fmt(convert(target), 1)}
              </p>
              <p className="mt-2 text-[12px] text-text-3" data-num>
                {remaining === null
                  ? 'Sin peso objetivo'
                  : Math.abs(remaining) < 0.1
                    ? '¡Conseguido!'
                    : `A ${fmt(Math.abs(convert(remaining)), 1)} ${unit}`}
              </p>
            </div>
          </section>

          <AnimatePresence>
            {recalc && (
              <motion.section
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
                aria-label="Sugerencia de recalcular objetivos"
              >
                <div className="rounded-lg bg-info-soft p-4">
                  <p className="text-[15px] font-semibold text-text">Tu peso ha cambiado {fmt(Math.abs(convert(recalc.to_kg - recalc.from_kg)), 1)} {unit}</p>
                  <p className="mt-1 text-[13.5px] leading-relaxed text-text-2" data-num>
                    Tus objetivos se calcularon con {fmt(convert(recalc.from_kg), 1)} {unit}. Con el peso actual serían {fmt(recalc.kcal)} kcal, {fmt(recalc.protein)} g de
                    proteína, {fmt(recalc.carbs)} g de hidratos y {fmt(recalc.fat)} g de grasas.
                  </p>
                  <div className="mt-3 flex gap-2">
                    <Button size="sm" onClick={recalculate} loading={recalculating} disabled={!online} icon={<RefreshCw className="size-4" aria-hidden />}>
                      Recalcular
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setDismissed(true)}>
                      Ahora no
                    </Button>
                  </div>
                </div>
              </motion.section>
            )}
          </AnimatePresence>

          <section className="card p-4" aria-labelledby="w-chart">
            <div className="flex items-center justify-between gap-3">
              <h2 id="w-chart" className="text-[15px] font-semibold text-text">
                Evolución
              </h2>
              <Segmented
                label="Periodo"
                size="sm"
                value={range}
                onChange={setRange}
                className="w-[210px]"
                options={[
                  { value: '30', label: '30 d', ariaLabel: '30 días' },
                  { value: '90', label: '90 d', ariaLabel: '90 días' },
                  { value: 'all', label: 'Todo' },
                ]}
              />
            </div>
            <div className="mt-3">
              <Suspense fallback={<Skeleton className="h-[261px]" />}>
                <WeightChart entries={visible} target={target} unit={unit} convert={convert} />
              </Suspense>
            </div>
          </section>

          <section aria-labelledby="w-list">
            <h2 id="w-list" className="eyebrow">
              Pesadas
            </h2>
            <ul className="card mt-2 divide-y divide-border overflow-hidden">
              <AnimatePresence initial={false}>
                {[...entries]
                  .reverse()
                  .slice(0, 40)
                  .map((entry, index, list) => {
                    const previous = list[index + 1]
                    const delta = previous ? entry.kg - previous.kg : null
                    return (
                      <motion.li
                        key={entry.date}
                        layout="position"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="flex items-center gap-3 overflow-hidden pr-1.5 pl-4"
                      >
                        <div className="min-w-0 flex-1 py-2.5">
                          <p className="text-[15px] font-medium text-text">{capitalize(relativeDay(entry.date))}</p>
                          <p className="mt-0.5 text-[12.5px] text-text-3" data-num>
                            Media: {fmt(convert(entry.avg), 1)} {unit}
                          </p>
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="text-[16px] font-semibold text-text" data-num>
                            {fmt(convert(entry.kg), 1)} <span className="text-[12px] font-medium text-text-3">{unit}</span>
                          </p>
                          {delta !== null && Math.abs(delta) >= 0.05 && (
                            <p className="text-[12px] text-text-3" data-num>
                              {fmtSigned(convert(delta), 1)}
                            </p>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => remove(entry)}
                          aria-label={`Borrar la pesada de ${relativeDay(entry.date).toLowerCase()}`}
                          className="grid size-11 shrink-0 place-items-center rounded-full text-text-3 hover:text-danger-text"
                        >
                          <Trash2 className="size-4" aria-hidden />
                        </button>
                      </motion.li>
                    )
                  })}
              </AnimatePresence>
            </ul>
          </section>
        </div>
      )}

      <Sheet
        open={sheet}
        onClose={() => setSheet(false)}
        title="Apuntar peso"
        footer={
          <Button size="lg" block onClick={save}>
            Guardar
          </Button>
        }
      >
        <div className="pt-4 pb-2">
          <Stepper label="Peso" value={draft} onChange={setDraft} step={0.1} decimals={1} min={unit === 'lb' ? 66 : 30} max={unit === 'lb' ? 660 : 300} unit={unit} />
          <label className="mt-7 flex min-h-11 items-center justify-between gap-3 text-[14.5px] text-text-2">
            Día de la pesada
            <input
              type="date"
              value={date}
              max={today}
              onChange={(event) => event.target.value && setDate(event.target.value)}
              className="h-11 rounded-sm border border-border bg-surface-2 px-2.5 text-text"
            />
          </label>
          <p className="mt-3 text-[13px] leading-relaxed text-text-3">
            El peso sube y baja cada día por agua, sal o digestión. La media de 7 días filtra ese ruido y enseña la tendencia real.
          </p>
        </div>
      </Sheet>
    </main>
  )
}

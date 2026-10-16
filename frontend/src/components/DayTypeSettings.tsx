import clsx from 'clsx'
import { Dumbbell, Moon, Pencil, RotateCcw, Scale } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useApp, usePrefsActions } from '@/hooks/data'
import { balancesRest, DEFAULT_TRAINING_DAYS, restAdjust, targetsFor, trainingAdjust, trainingDaysText } from '@/lib/dayTargets'
import { fmt, fmtSigned } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { GRAM_MACROS } from '@/lib/macros'
import type { DayKind, DayTargetsValues } from '@/lib/types'
import { Button } from '@/ui/Button'
import { NumberInput, Stepper } from '@/ui/Field'
import { Notice } from '@/ui/Notice'
import { Sheet } from '@/ui/Sheet'
import { Switch } from '@/ui/Switch'
import { toast } from '@/ui/toast'

const WEEKDAYS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
const WEEKDAY_NAMES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

function TargetsLine({ values }: { values: DayTargetsValues }) {
  return (
    <span className="text-[13px] text-text-3" data-num>
      {fmt(values.kcal)} kcal ·{' '}
      {GRAM_MACROS.map((m, i) => (
        <span key={m.key}>
          {i > 0 && ' · '}
          <span className="font-semibold" style={{ color: m.text }}>
            {m.letter}
          </span>{' '}
          {fmt(values[m.key as 'protein' | 'carbs' | 'fat'])}
        </span>
      ))}
    </span>
  )
}

/** Ajustes de los objetivos por tipo de día: días de entreno, ajuste de cada tipo y objetivos fijados a mano. */
/** Niveles de actividad que ya incluyen entrenar varios días por semana. */
const ACTIVE = new Set(['ligero', 'medio', 'moderado', 'alto', 'muy_alto'])

export function DayTypeSettings() {
  const app = useApp()
  const save = usePrefsActions()
  const prefs = app.prefs ?? { water_goal_ml: null }
  const enabled = !!prefs.day_types
  const days = prefs.training_days ?? DEFAULT_TRAINING_DAYS
  const [editing, setEditing] = useState<DayKind | null>(null)
  const base = app.targets

  const kinds: { kind: DayKind; label: string; Icon: typeof Dumbbell; adjust: number; manual: DayTargetsValues | null | undefined }[] = [
    { kind: 'entreno', label: 'Días de entreno', Icon: Dumbbell, adjust: trainingAdjust(prefs), manual: prefs.training_targets },
    { kind: 'descanso', label: 'Días de descanso', Icon: Moon, adjust: restAdjust(base.kcal, prefs), manual: prefs.rest_targets },
  ]

  return (
    <>
      <Switch
        label="Objetivos distintos para entreno y descanso"
        description={enabled ? 'Los hidratos suben o bajan; la proteína y la grasa, igual.' : 'Ahora todos los días tienen el mismo objetivo.'}
        checked={enabled}
        onChange={(on) => {
          save({ day_types: on })
          toast.success(on ? 'Objetivos por tipo de día activados' : 'Mismo objetivo todos los días')
        }}
      />
      {enabled && (
        <>
          <div className="border-t border-border px-4 py-3">
            <p className="text-[14px] text-text">Días de entreno habituales</p>
            <div role="group" aria-label="Días de entreno habituales" className="mt-2 grid grid-cols-7 gap-1.5">
              {WEEKDAYS.map((letter, index) => {
                const on = days.includes(index)
                return (
                  <button
                    key={letter}
                    type="button"
                    aria-pressed={on}
                    aria-label={WEEKDAY_NAMES[index]}
                    onClick={() => {
                      haptic('select')
                      save({ training_days: on ? days.filter((d) => d !== index) : [...days, index].sort() })
                    }}
                    className={clsx(
                      'h-11 rounded-sm border text-[14px] font-semibold transition-colors',
                      on ? 'border-accent bg-accent-soft text-accent-text' : 'border-border bg-surface-2 text-text-3',
                    )}
                  >
                    {letter}
                  </button>
                )
              })}
            </div>
            <p className="mt-2 text-[12.5px] text-text-3">Un día concreto se cambia desde Hoy, tocando su tipo.</p>
          </div>
          {kinds.map(({ kind, label, Icon, adjust, manual }) => (
            <div key={kind} className="border-t border-border px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <p className="flex items-center gap-2 text-[14px] text-text">
                  <Icon className="size-4 text-text-3" aria-hidden />
                  {label}
                </p>
                <button
                  type="button"
                  onClick={() => setEditing(kind)}
                  className="-mr-2 inline-flex min-h-11 items-center gap-1.5 rounded-full px-3 text-[13.5px] font-medium text-accent-text"
                >
                  <Pencil className="size-3.5" aria-hidden />
                  {manual ? 'A mano' : `${fmtSigned(adjust)} kcal`}
                </button>
              </div>
              <TargetsLine values={targetsFor(base, prefs, kind)} />
              {kind === 'descanso' && !manual && balancesRest(prefs) && (
                <p className="mt-1 text-[12.5px] text-text-3">Compensan los días de entreno: de media, la semana queda en tu objetivo.</p>
              )}
            </div>
          ))}
        </>
      )}
      <div className="border-t border-border">
        <Switch
          label="Sumar las calorías del entreno al objetivo"
          description={
            app.targets?.tdee_mode === 'real'
              ? 'Con tu gasto real no se suman: ese gasto ya incluye lo que entrenas.'
              : prefs.add_exercise_kcal
                ? `Lo entrenado (calorías netas, sin el gasto en reposo) se suma ese día en forma de hidratos.${
                    ACTIVE.has(app.profile.activity) ? ' Tu nivel de actividad ya cuenta el gimnasio: si las sumas, elige uno que no lo incluya.' : ''
                  }`
                : 'Ahora solo se muestran como referencia. Es una estimación, no una medida.'
          }
          checked={!!prefs.add_exercise_kcal}
          onChange={(on) => save({ add_exercise_kcal: on })}
        />
      </div>
      <DayKindSheet kind={editing} onClose={() => setEditing(null)} />
    </>
  )
}

function DayKindSheet({ kind, onClose }: { kind: DayKind | null; onClose: () => void }) {
  const app = useApp()
  const save = usePrefsActions()
  const prefs = app.prefs ?? { water_goal_ml: null }
  const training = kind === 'entreno'
  const manual = training ? prefs.training_targets : prefs.rest_targets
  const [mode, setMode] = useState<'balance' | 'adjust' | 'manual'>('adjust')
  const [adjust, setAdjust] = useState(0)
  const [values, setValues] = useState<DayTargetsValues>(app.targets)

  useEffect(() => {
    if (!kind) return
    setMode(manual ? 'manual' : !training && balancesRest(prefs) ? 'balance' : 'adjust')
    setAdjust(training ? trainingAdjust(prefs) : restAdjust(app.targets.kcal, prefs))
    setValues(manual ?? targetsFor(app.targets, prefs, kind))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind])

  const dailyTraining = new Set(prefs.training_days ?? DEFAULT_TRAINING_DAYS).size === 7
  const preview =
    mode === 'manual'
      ? values
      : mode === 'balance'
        ? targetsFor(app.targets, { ...prefs, rest_targets: null, balance_rest: true }, kind)
        : training
          ? targetsFor(app.targets, { ...prefs, training_targets: null, training_kcal_adjust: adjust }, kind)
          : targetsFor(app.targets, { ...prefs, rest_targets: null, rest_kcal_adjust: adjust, balance_rest: false }, kind)
  const invalid = mode === 'manual' && (values.kcal < 800 || values.protein < 20 || values.fat < 10)

  function submit() {
    if (!kind || invalid) return
    if (mode === 'manual') save(training ? { training_targets: values } : { rest_targets: values })
    else if (mode === 'balance') save({ balance_rest: true, rest_targets: null })
    else save(training ? { training_kcal_adjust: adjust, training_targets: null } : { rest_kcal_adjust: adjust, rest_targets: null, balance_rest: false })
    haptic('success')
    toast.success(training ? 'Objetivo de entreno guardado' : 'Objetivo de descanso guardado', `${fmt(preview.kcal)} kcal`)
    onClose()
  }

  return (
    <Sheet
      open={!!kind}
      onClose={onClose}
      title={training ? 'Días de entreno' : 'Días de descanso'}
      footer={
        <Button size="lg" block disabled={invalid} onClick={submit}>
          Guardar
        </Button>
      }
    >
      <div className="space-y-5">
        {mode === 'balance' ? (
          <>
            <p className="text-[14.5px] leading-relaxed text-text-2">
              Bajan lo justo para compensar lo que suben tus días de entreno ({trainingDaysText(prefs.training_days ?? DEFAULT_TRAINING_DAYS)}): así la media de
              la semana es tu objetivo de siempre ({fmt(app.targets.kcal)} kcal). Ahora mismo, {fmtSigned(restAdjust(app.targets.kcal, prefs))} kcal en hidratos.
            </p>
            <Button variant="ghost" size="sm" block onClick={() => setMode('adjust')} icon={<Pencil className="size-4" aria-hidden />}>
              Prefiero elegir el ajuste yo
            </Button>
            <Button variant="ghost" size="sm" block onClick={() => setMode('manual')} icon={<Pencil className="size-4" aria-hidden />}>
              Prefiero fijar las cifras a mano
            </Button>
          </>
        ) : mode === 'adjust' ? (
          <>
            <p className="text-[14.5px] leading-relaxed text-text-2">
              Parte de tu objetivo de siempre ({fmt(app.targets.kcal)} kcal) y suma o resta calorías en forma de hidratos.
              {training && balancesRest(prefs) && ' Los días de descanso bajan lo mismo, repartido, para que la media de la semana no cambie.'}
            </p>
            {training && dailyTraining && balancesRest(prefs) && (
              <Notice level="info">Entrenas todos los días: no hay días de descanso con los que compensar, así que no se suma nada.</Notice>
            )}
            <Stepper label="Ajuste de calorías" value={adjust} onChange={setAdjust} step={50} min={-800} max={800} unit="kcal" />
            {!training && (
              <Button variant="ghost" size="sm" block onClick={() => setMode('balance')} icon={<Scale className="size-4" aria-hidden />}>
                Compensar los días de entreno automáticamente
              </Button>
            )}
            <Button variant="ghost" size="sm" block onClick={() => setMode('manual')} icon={<Pencil className="size-4" aria-hidden />}>
              Prefiero fijar las cifras a mano
            </Button>
          </>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              {(
                [
                  ['kcal', 'Calorías', 'kcal'],
                  ['protein', 'Proteínas', 'g'],
                  ['carbs', 'Hidratos', 'g'],
                  ['fat', 'Grasas', 'g'],
                ] as const
              ).map(([key, label, suffix]) => (
                <label key={key} className="block">
                  <span className="mb-1.5 block text-[13px] font-medium text-text-2">{label}</span>
                  <span className="flex h-12 items-center rounded-md border border-border bg-surface-2 px-3.5 focus-within:border-accent">
                    <NumberInput
                      value={values[key]}
                      onChange={(value) => setValues((v) => ({ ...v, [key]: Math.round(value ?? 0) }))}
                      decimals={0}
                      min={0}
                      max={8000}
                      ariaLabel={`${label} en días de ${training ? 'entreno' : 'descanso'}`}
                      className="min-w-0 flex-1 text-text"
                    />
                    <span className="text-[13px] text-text-3">{suffix}</span>
                  </span>
                </label>
              ))}
            </div>
            {invalid && <Notice level="warn">Revisa las cifras: mínimo 800 kcal, 20 g de proteína y 10 g de grasa.</Notice>}
            <Button
              variant="ghost"
              size="sm"
              block
              onClick={() => setMode(!training && balancesRest(prefs) ? 'balance' : 'adjust')}
              icon={<RotateCcw className="size-4" aria-hidden />}
            >
              Volver a calcularlo
            </Button>
          </>
        )}
        <div className="rounded-md bg-surface-2 p-3.5">
          <p className="text-[12.5px] font-semibold text-text-2">Quedaría así</p>
          <TargetsLine values={preview} />
        </div>
        <p className="text-[12.5px] leading-relaxed text-text-3">Son orientaciones generales, no consejo médico.</p>
      </div>
    </Sheet>
  )
}

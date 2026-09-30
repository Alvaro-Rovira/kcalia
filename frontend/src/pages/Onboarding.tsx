import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { ArrowLeft, ArrowRight, Camera, Check, Mars, Mic, Sparkles, Venus, Zap } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Logo, Wordmark } from '@/components/Logo'
import { PlanExplanation } from '@/components/PlanExplanation'
import { api, errorMessage } from '@/lib/api'
import { todayISO } from '@/lib/dates'
import { haptic } from '@/lib/haptics'
import { GRAM_MACROS } from '@/lib/macros'
import { ACTIVITIES, GOALS } from '@/lib/options'
import type { Activity, Bootstrap, Goal, Plan, Profile, ProfileInput, Sex, Targets } from '@/lib/types'
import { keys } from '@/offline/queryClient'
import { AnimatedNumber } from '@/ui/AnimatedNumber'
import { Button, IconButton } from '@/ui/Button'
import { Stepper } from '@/ui/Field'
import { Notice } from '@/ui/Notice'
import { Ring } from '@/ui/Ring'
import { Skeleton } from '@/ui/Skeleton'
import { toast } from '@/ui/toast'

interface Answers {
  sex: Sex | null
  age: number
  weight_kg: number
  height_cm: number
  activity: Activity | null
  goal: Goal | null
  target_weight_kg: number | null
}

const STEPS = ['intro', 'sex', 'age', 'weight', 'height', 'activity', 'goal', 'target', 'plan'] as const
type Step = (typeof STEPS)[number]
const QUESTIONS = STEPS.length - 2

function Choice({
  selected,
  onClick,
  icon,
  title,
  text,
  tag,
}: {
  selected: boolean
  onClick: () => void
  icon: ReactNode
  title: string
  text?: string
  tag?: string
}) {
  return (
    <motion.button
      type="button"
      role="radio"
      aria-checked={selected}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className={clsx(
        'flex w-full items-center gap-3.5 rounded-lg border p-4 text-left transition-colors',
        selected ? 'border-accent bg-accent-soft' : 'border-border bg-surface hover:border-border-strong',
      )}
    >
      <span
        className={clsx(
          'grid size-11 shrink-0 place-items-center rounded-full transition-colors',
          selected ? 'bg-accent text-on-accent' : 'bg-surface-2 text-text-2',
        )}
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[16px] font-semibold tracking-[-0.01em] text-text">{title}</span>
        {text && <span className="mt-0.5 block text-[13.5px] leading-snug text-text-2">{text}</span>}
      </span>
      {tag && (
        <span className="shrink-0 rounded-full bg-surface-2 px-2.5 py-1 text-[12.5px] font-semibold text-text-2" data-num>
          {tag}
        </span>
      )}
    </motion.button>
  )
}

function Question({ title, text, children }: { title: string; text?: string; children: ReactNode }) {
  return (
    <div>
      <h1 className="text-[28px] leading-[1.15] font-semibold tracking-[-0.03em] text-text">{title}</h1>
      {text && <p className="mt-2.5 text-[15.5px] leading-relaxed text-text-2">{text}</p>}
      <div className="mt-8">{children}</div>
    </div>
  )
}

export default function Onboarding() {
  const client = useQueryClient()
  const reduce = useReducedMotion()
  const [index, setIndex] = useState(0)
  const [direction, setDirection] = useState(0)
  const [answers, setAnswers] = useState<Answers>({
    sex: null,
    age: 30,
    weight_kg: 75,
    height_cm: 172,
    activity: null,
    goal: null,
    target_weight_kg: null,
  })
  const [plan, setPlan] = useState<Plan | null>(null)
  const [saving, setSaving] = useState(false)
  const step: Step = STEPS[index]

  const set = <K extends keyof Answers>(key: K, value: Answers[K]) => setAnswers((a) => ({ ...a, [key]: value }))
  const go = (delta: number) => {
    setDirection(delta)
    setIndex((i) => Math.min(STEPS.length - 1, Math.max(0, i + delta)))
  }
  /** En las preguntas de elegir, tocar una opción avanza sola tras un instante. */
  const pick = <K extends keyof Answers>(key: K, value: Answers[K]) => {
    haptic('select')
    set(key, value)
    setTimeout(() => go(1), reduce ? 0 : 260)
  }

  const payload: ProfileInput | null =
    answers.sex && answers.activity && answers.goal
      ? {
          sex: answers.sex,
          age: answers.age,
          weight_kg: answers.weight_kg,
          height_cm: answers.height_cm,
          activity: answers.activity,
          goal: answers.goal,
          target_weight_kg: answers.target_weight_kg,
        }
      : null

  useEffect(() => {
    if (step !== 'plan' || !payload) return
    let cancelled = false
    setPlan(null)
    api
      .post<Plan>('/api/plan/preview', payload)
      .then((result) => {
        if (!cancelled) {
          setPlan(result)
          haptic('success')
        }
      })
      .catch((error) => {
        if (!cancelled) {
          toast.error('No he podido calcular tu plan', errorMessage(error))
          go(-1)
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step])

  async function finish() {
    if (!payload || saving) return
    setSaving(true)
    try {
      const saved = await api.put<{ profile: Profile; targets: Targets; plan: Plan }>('/api/profile', {
        ...payload,
        today: todayISO(),
      })
      haptic('success')
      client.setQueryData<Bootstrap>(keys.bootstrap, (old) => (old ? { ...old, ...saved } : old))
      await client.invalidateQueries()
    } catch (error) {
      toast.error('No se ha podido guardar', errorMessage(error))
      setSaving(false)
    }
  }

  const canContinue =
    step === 'sex' ? !!answers.sex : step === 'activity' ? !!answers.activity : step === 'goal' ? !!answers.goal : true
  const isQuestion = index >= 1 && index <= QUESTIONS
  const variants = {
    enter: (d: number) => (d === 0 ? { opacity: 1, x: 0 } : reduce ? { opacity: 0 } : { opacity: 0, x: d > 0 ? 44 : -44 }),
    center: { opacity: 1, x: 0 },
    exit: (d: number) => (reduce ? { opacity: 0 } : { opacity: 0, x: d > 0 ? -44 : 44 }),
  }

  return (
    <div
      className="mx-auto flex min-h-dvh w-full max-w-[520px] flex-col px-6"
      style={{ paddingTop: 'calc(var(--safe-t) + 10px)', paddingBottom: 'calc(var(--safe-b) + 20px)' }}
    >
      <header className="flex h-14 shrink-0 items-center gap-3">
        {index > 0 ? (
          <IconButton label="Volver a la pregunta anterior" onClick={() => go(-1)} className="-ml-2.5">
            <ArrowLeft className="size-5" aria-hidden />
          </IconButton>
        ) : (
          <span className="size-6" />
        )}
        {isQuestion && (
          <>
            <div
              className="h-1.5 flex-1 overflow-hidden rounded-full bg-track"
              role="progressbar"
              aria-label="Progreso del cuestionario"
              aria-valuemin={0}
              aria-valuemax={QUESTIONS}
              aria-valuenow={index}
            >
              <motion.div
                className="h-full rounded-full bg-accent"
                initial={false}
                animate={{ width: `${(index / QUESTIONS) * 100}%` }}
                transition={{ type: 'spring', stiffness: 260, damping: 32 }}
              />
            </div>
            <span className="w-9 text-right text-[13px] font-medium text-text-3" data-num aria-hidden>
              {index}/{QUESTIONS}
            </span>
          </>
        )}
      </header>

      <main className="relative flex min-h-0 flex-1 flex-col pt-5">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={step}
            custom={direction}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-1 flex-col"
          >
            {step === 'intro' && (
              <div className="flex flex-1 flex-col justify-center pb-10">
                <div className="flex items-center gap-3">
                  <Logo size={56} />
                  <Wordmark className="text-[36px]" />
                </div>
                <h1 className="mt-8 text-[32px] leading-[1.1] font-semibold tracking-[-0.035em] text-text">
                  Calorías y macros,
                  <br />
                  con calma.
                </h1>
                <p className="mt-3 text-[16px] leading-relaxed text-text-2">
                  Siete preguntas rápidas y te preparo un plan a tu medida. Luego solo tendrás que contarme qué comes.
                </p>
                <ul className="mt-8 space-y-4">
                  {[
                    { Icon: Sparkles, text: 'Escribe «dos huevos con tostada» y yo calculo los macros.' },
                    { Icon: Camera, text: 'O haz una foto del plato.' },
                    { Icon: Mic, text: 'O díctalo si vas con prisa.' },
                    { Icon: Zap, text: 'Lo que repites se recuerda: sin esperas ni gasto.' },
                  ].map(({ Icon, text }, i) => (
                    <motion.li
                      key={text}
                      initial={reduce ? false : { opacity: 0, x: -12 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.15 + i * 0.08, duration: 0.4 }}
                      className="flex items-center gap-3.5 text-[15px] text-text"
                    >
                      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent-text">
                        <Icon className="size-[18px]" aria-hidden />
                      </span>
                      {text}
                    </motion.li>
                  ))}
                </ul>
              </div>
            )}

            {step === 'sex' && (
              <Question title="¿Cuál es tu sexo?" text="La fórmula del metabolismo basal usa una constante distinta para cada uno.">
                <div role="radiogroup" aria-label="Sexo" className="space-y-3">
                  <Choice selected={answers.sex === 'hombre'} onClick={() => pick('sex', 'hombre')} icon={<Mars className="size-5" aria-hidden />} title="Hombre" />
                  <Choice selected={answers.sex === 'mujer'} onClick={() => pick('sex', 'mujer')} icon={<Venus className="size-5" aria-hidden />} title="Mujer" />
                </div>
              </Question>
            )}

            {step === 'age' && (
              <Question title="¿Cuántos años tienes?" text="El gasto en reposo baja un poco con la edad.">
                <Stepper label="Edad" value={answers.age} onChange={(v) => set('age', Math.round(v))} min={14} max={100} unit="años" />
              </Question>
            )}

            {step === 'weight' && (
              <Question title="¿Cuánto pesas ahora?" text="Mejor en ayunas y sin ropa. Podrás actualizarlo cuando quieras.">
                <Stepper label="Peso" value={answers.weight_kg} onChange={(v) => set('weight_kg', v)} step={0.5} decimals={1} min={30} max={300} unit="kg" />
              </Question>
            )}

            {step === 'height' && (
              <Question title="¿Cuánto mides?">
                <Stepper label="Altura" value={answers.height_cm} onChange={(v) => set('height_cm', Math.round(v))} min={120} max={230} unit="cm" />
              </Question>
            )}

            {step === 'activity' && (
              <Question title="¿Cuánto te mueves?" text="Cuenta el entrenamiento y también tu día a día.">
                <div role="radiogroup" aria-label="Nivel de actividad" className="space-y-2.5">
                  {ACTIVITIES.map(({ value, label, text, Icon, factor }) => (
                    <Choice
                      key={value}
                      selected={answers.activity === value}
                      onClick={() => pick('activity', value)}
                      icon={<Icon className="size-5" aria-hidden />}
                      title={label}
                      text={text}
                      tag={`×${String(factor).replace('.', ',')}`}
                    />
                  ))}
                </div>
              </Question>
            )}

            {step === 'goal' && (
              <Question title="¿Qué quieres conseguir?" text="El porcentaje es el ajuste sobre tus calorías de mantenimiento.">
                <div role="radiogroup" aria-label="Objetivo" className="space-y-2.5">
                  {GOALS.map(({ value, label, text, tag, Icon }) => (
                    <Choice
                      key={value}
                      selected={answers.goal === value}
                      onClick={() => pick('goal', value)}
                      icon={<Icon className="size-5" aria-hidden />}
                      title={label}
                      text={text}
                      tag={tag}
                    />
                  ))}
                </div>
              </Question>
            )}

            {step === 'target' && (
              <Question title="¿Tienes un peso objetivo?" text="Es opcional. Sirve para estimar cuánto falta y avisarte cuando llegues.">
                {answers.target_weight_kg === null ? (
                  <Button variant="secondary" size="lg" block onClick={() => set('target_weight_kg', answers.weight_kg)}>
                    Sí, quiero ponerlo
                  </Button>
                ) : (
                  <>
                    <Stepper
                      label="Peso objetivo"
                      value={answers.target_weight_kg}
                      onChange={(v) => set('target_weight_kg', v)}
                      step={0.5}
                      decimals={1}
                      min={30}
                      max={300}
                      unit="kg"
                    />
                    <button
                      type="button"
                      onClick={() => set('target_weight_kg', null)}
                      className="mx-auto mt-6 block min-h-11 px-4 text-[14.5px] font-medium text-text-3 underline-offset-4 hover:underline"
                    >
                      Prefiero no ponerlo
                    </button>
                  </>
                )}
              </Question>
            )}

            {step === 'plan' && <PlanReveal plan={plan} targetWeight={answers.target_weight_kg} />}
          </motion.div>
        </AnimatePresence>
      </main>

      <footer className="shrink-0 pt-5">
        {step === 'plan' ? (
          <Button size="lg" block onClick={finish} loading={saving} disabled={!plan} icon={<Check className="size-5" aria-hidden />}>
            Empezar con este plan
          </Button>
        ) : (
          <Button size="lg" block onClick={() => go(1)} disabled={!canContinue}>
            {step === 'intro' ? 'Empezar' : step === 'target' ? (answers.target_weight_kg === null ? 'Saltar' : 'Ver mi plan') : 'Continuar'}
            <ArrowRight className="size-5" aria-hidden />
          </Button>
        )}
      </footer>
    </div>
  )
}

function PlanReveal({ plan, targetWeight }: { plan: Plan | null; targetWeight: number | null }) {
  if (!plan) {
    return (
      <div role="status" aria-label="Calculando tu plan" className="space-y-5">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mx-auto size-[200px] !rounded-full" />
        <div className="grid grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-40" />
      </div>
    )
  }
  return (
    <div className="pb-2">
      <p className="eyebrow">Tu plan</p>
      <h1 className="mt-1 text-[28px] leading-tight font-semibold tracking-[-0.03em] text-text">{plan.goal_label}</h1>

      <div className="mt-6 flex justify-center">
        <Ring progress={1} size={204} stroke={16} color="var(--kcal)" from="var(--kcal-from)" glow label={`Objetivo: ${plan.kcal} kilocalorías al día`}>
          <div className="text-center">
            <AnimatedNumber value={plan.kcal} duration={1.4} className="block text-[46px] leading-none font-semibold tracking-[-0.04em] text-text" />
            <span className="mt-1.5 block text-[14px] font-medium text-text-2">kcal al día</span>
          </div>
        </Ring>
      </div>

      <div className="mt-6 grid grid-cols-3 gap-3">
        {GRAM_MACROS.map((m, i) => (
          <motion.div
            key={m.key}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 + i * 0.1, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="card p-3.5"
          >
            <div className="flex items-center gap-1.5">
              <span className="grid size-6 place-items-center rounded-full text-[12px] font-bold" style={{ background: m.soft, color: m.text }} aria-hidden>
                {m.letter}
              </span>
              <span className="text-[12.5px] font-medium text-text-2">{m.label}</span>
            </div>
            <p className="mt-2.5 text-[26px] leading-none font-semibold tracking-[-0.03em] text-text">
              <AnimatedNumber value={plan[m.key]} duration={1.2} />
              <span className="ml-1 text-[14px] font-medium text-text-3">g</span>
            </p>
          </motion.div>
        ))}
      </div>

      {plan.warnings.length > 0 && (
        <div className="mt-4 space-y-2.5">
          {plan.warnings.map((w) => (
            <Notice key={w.code} level={w.level}>
              {w.text}
            </Notice>
          ))}
        </div>
      )}

      <PlanExplanation plan={plan} targetWeight={targetWeight} className="mt-4" />
    </div>
  )
}

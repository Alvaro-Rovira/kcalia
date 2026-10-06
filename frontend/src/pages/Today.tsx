import clsx from 'clsx'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Activity, CopyPlus, Dumbbell, Flame, Leaf, Lightbulb, Moon, Plus, Wine } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { CopyPanel } from '@/components/CopyPanel'
import { DateStrip } from '@/components/DateStrip'
import { MealRow } from '@/components/MealRow'
import { MealSheet } from '@/components/MealSheet'
import { SuggestCard } from '@/components/SuggestCard'
import { WaterCard } from '@/components/WaterCard'
import { useShell } from '@/components/Shell'
import { useApp, useDayTargets, useDayTypeActions, useMealActions, useMeals, useStats } from '@/hooks/data'
import { dailyTip } from '@/lib/coach'
import { copyInputs } from '@/lib/copy'
import { KIND_LABEL, targetsFor } from '@/lib/dayTargets'
import { addDays, fmtLong, greeting, isValidISO, relativeDay, todayISO } from '@/lib/dates'
import { capitalize, fmt, plural } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { FIBER_TARGET, GRAM_MACROS, mealsExtras, sumMacros } from '@/lib/macros'
import { SLOTS } from '@/lib/slots'
import type { Meal } from '@/lib/types'
import { AnimatedNumber } from '@/ui/AnimatedNumber'
import { Button } from '@/ui/Button'
import { EmptyState } from '@/ui/EmptyState'
import { Ring } from '@/ui/Ring'
import { Sheet } from '@/ui/Sheet'
import { Skeleton } from '@/ui/Skeleton'
import { toast } from '@/ui/toast'

const TIP_STYLE = {
  kcal: { box: 'bg-kcal-soft', icon: 'text-kcal-text' },
  protein: { box: 'bg-protein-soft', icon: 'text-protein-text' },
  warn: { box: 'bg-warn-soft', icon: 'text-warn-text' },
  neutral: { box: 'bg-surface-2', icon: 'text-text-3' },
}

/** Celebra una sola vez por día y por motivo, aunque se borre y se vuelva a añadir. */
function celebrateOnce(date: string, kind: 'kcal' | 'protein'): boolean {
  const key = `kcalia:celebrated:${date}:${kind}`
  try {
    if (localStorage.getItem(key)) return false
    localStorage.setItem(key, '1')
  } catch {
    // Sin almacenamiento, se celebra (como mucho, una vez por sesión y cruce).
  }
  return true
}

export default function Today() {
  const app = useApp()
  const dayTargets = useDayTargets()
  const setDayType = useDayTypeActions()
  const { openAddMeal, celebrate } = useShell()
  const actions = useMealActions()
  const reduce = useReducedMotion()
  const [params, setParams] = useSearchParams()
  const today = todayISO()
  const date = isValidISO(params.get('fecha')) && params.get('fecha')! <= today ? params.get('fecha')! : today
  const isToday = date === today
  const day = dayTargets(date)
  const targets = { ...app.targets, ...day.targets }
  const [direction, setDirection] = useState(0)
  const [detail, setDetail] = useState<Meal | null>(null)
  const [copyDay, setCopyDay] = useState(false)

  const meals = useMeals(date)
  const stats = useStats()
  const list = useMemo(() => meals.data ?? [], [meals.data])
  const eaten = useMemo(() => sumMacros(list), [list])
  const extras = useMemo(() => mealsExtras(list), [list])
  const loading = meals.isPending

  const setDate = (next: string) => {
    if (next > today || next === date) return
    setDirection(next > date ? 1 : -1)
    setParams(next === today ? {} : { fecha: next }, { replace: true })
  }

  const remaining = targets.kcal - eaten.kcal
  const over = remaining < 0
  const onTarget = eaten.kcal >= targets.kcal * 0.9 && eaten.kcal <= targets.kcal * 1.1
  const proteinDone = eaten.protein >= targets.protein * 0.9
  const tip = dailyTip(eaten, targets, list.length, isToday)

  // Celebración sutil al cruzar un objetivo, solo como consecuencia de añadir algo hoy.
  const previous = useRef<{ date: string; onTarget: boolean; proteinDone: boolean } | null>(null)
  useEffect(() => {
    if (loading) return
    const before = previous.current
    previous.current = { date, onTarget, proteinDone }
    if (!isToday || !before || before.date !== date) return
    if (!before.proteinDone && proteinDone && celebrateOnce(date, 'protein')) {
      celebrate()
      toast({ tone: 'success', title: 'Proteína del día cumplida', description: 'Tus músculos te lo agradecen.' })
    } else if (!before.onTarget && onTarget && celebrateOnce(date, 'kcal')) {
      celebrate()
      toast({ tone: 'success', title: 'Calorías en objetivo', description: 'Justo donde tenían que estar.' })
    }
  }, [loading, date, isToday, onTarget, proteinDone, celebrate])

  function copyAll(target: { date: string }) {
    const copies = copyInputs(list, target)
    for (const input of copies) actions.add(input)
    haptic('success')
    setCopyDay(false)
    toast({
      tone: 'success',
      title: `${copies.length} ${plural(copies.length, 'comida copiada', 'comidas copiadas')} a ${relativeDay(target.date).toLowerCase()}`,
      description: 'Sin gastar IA',
      action: target.date !== date ? { label: 'Ver', onClick: () => setDate(target.date) } : undefined,
    })
  }

  function remove(meal: Meal) {
    actions.remove(meal)
    toast({
      title: 'Comida borrada',
      description: meal.name,
      action: { label: 'Deshacer', onClick: () => actions.restore(meal) },
    })
  }

  const groups = SLOTS.map((slot) => ({ ...slot, meals: list.filter((m) => m.slot === slot.key) })).filter((g) => g.meals.length > 0)
  // Posición global de cada comida, para escalonar la entrada de toda la lista.
  const groupOffset = Object.fromEntries(groups.map((g, i) => [g.key, groups.slice(0, i).reduce((n, x) => n + x.meals.length, 0)]))
  const streak = stats.data?.streak
  const tipStyle = TIP_STYLE[tip.tone]
  const slide = {
    // Dirección 0 = primer render: el contenedor ya está en su sitio y solo animan sus hijos.
    enter: (d: number) => (d === 0 ? { opacity: 1, x: 0 } : reduce ? { opacity: 0 } : { opacity: 0, x: d * 56 }),
    center: { opacity: 1, x: 0 },
    exit: (d: number) => (reduce || d === 0 ? { opacity: 0 } : { opacity: 0, x: d * -56 }),
  }

  return (
    <main className="page">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[14px] text-text-2">
            {isToday ? `${greeting()}, ${capitalize(app.user.username)}` : capitalize(fmtLong(date))}
          </p>
          <h1 className="mt-0.5 truncate text-[30px] leading-tight font-semibold tracking-[-0.035em] text-text">
            {capitalize(relativeDay(date))}
          </h1>
          {day.kind && (
            <button
              type="button"
              onClick={() => {
                const next = day.kind === 'entreno' ? 'descanso' : 'entreno'
                setDayType(date, next)
                haptic('select')
                toast({
                  title: `${KIND_LABEL[next]}: ${fmt(targetsFor(app.targets, app.prefs, next).kcal)} kcal`,
                  action: { label: 'Deshacer', onClick: () => setDayType(date, day.manual ? day.kind : null) },
                })
              }}
              aria-label={`${KIND_LABEL[day.kind]}. Cambiar a ${day.kind === 'entreno' ? 'descanso' : 'entreno'}`}
              className="mt-1.5 inline-flex h-9 items-center gap-1.5 rounded-full border border-border bg-surface px-3 text-[13px] font-medium text-text-2"
            >
              {day.kind === 'entreno' ? <Dumbbell className="size-3.5 text-accent-text" aria-hidden /> : <Moon className="size-3.5 text-text-3" aria-hidden />}
              {KIND_LABEL[day.kind]}
              <span className="text-text-3" data-num>
                · {fmt(day.targets.kcal)} kcal
              </span>
            </button>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2 pt-1.5">
          {!isToday && (
            <Button variant="secondary" size="sm" onClick={() => setDate(today)}>
              Ir a hoy
            </Button>
          )}
          {streak && streak.current > 0 && (
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="flex h-11 items-center gap-1.5 rounded-full border border-border bg-surface px-3.5"
              role="img"
              aria-label={`Racha de ${streak.current} días cumpliendo el objetivo`}
            >
              <Flame className={clsx('size-[18px]', streak.today_done ? 'fill-kcal-from text-kcal-from' : 'text-text-3')} aria-hidden />
              <span className="text-[15px] font-semibold text-text" data-num>
                {streak.current}
              </span>
            </motion.div>
          )}
        </div>
      </header>

      <div className="mt-4">
        <DateStrip date={date} onChange={setDate} targetKcal={(iso) => dayTargets(iso).targets.kcal} />
      </div>

      <AnimatePresence mode="wait" custom={direction}>
        <motion.div
          key={date}
          custom={direction}
          variants={slide}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          drag={reduce ? false : 'x'}
          dragDirectionLock
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.14}
          dragSnapToOrigin
          onDragEnd={(_, info) => {
            if (Math.abs(info.offset.x) < 90 && Math.abs(info.velocity.x) < 600) return
            setDate(addDays(date, info.offset.x > 0 ? -1 : 1))
          }}
          className="mt-4 lg:grid lg:grid-cols-[minmax(0,400px)_minmax(0,1fr)] lg:items-start lg:gap-7"
        >
          <div>
            <section className="card p-5" aria-label="Resumen del día">
              {loading ? (
                <div role="status" aria-label="Cargando el día">
                  <Skeleton className="mx-auto size-[212px] !rounded-full" />
                  <div className="mt-6 grid grid-cols-3 gap-3">
                    {[0, 1, 2].map((i) => (
                      <Skeleton key={i} className="h-[92px]" />
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex justify-center">
                    <motion.div
                      animate={onTarget && !reduce ? { scale: [1, 1.025, 1] } : { scale: 1 }}
                      transition={{ duration: 0.9, ease: 'easeInOut' }}
                      key={onTarget ? 'done' : 'open'}
                    >
                      <Ring
                        progress={eaten.kcal / targets.kcal}
                        size={212}
                        stroke={17}
                        color="var(--kcal)"
                        from="var(--kcal-from)"
                        glow
                        label={
                          over
                            ? `Calorías: ${fmt(eaten.kcal)} de ${fmt(targets.kcal)}. Te has pasado ${fmt(-remaining)} kilocalorías.`
                            : `Calorías: ${fmt(eaten.kcal)} de ${fmt(targets.kcal)}. Quedan ${fmt(remaining)} kilocalorías.`
                        }
                      >
                        <div className="text-center">
                          <span className="block text-[13px] font-medium text-text-2">{over ? 'Te has pasado' : isToday ? 'Te quedan' : 'Quedaron'}</span>
                          <AnimatedNumber
                            value={Math.abs(remaining)}
                            className={clsx('mt-1 block text-[50px] leading-none font-semibold tracking-[-0.045em]', over ? 'text-danger-text' : 'text-text')}
                          />
                          <span className="mt-1.5 block text-[13px] font-medium text-text-3">kcal</span>
                        </div>
                      </Ring>
                    </motion.div>
                  </div>

                  <dl className="mt-5 grid grid-cols-2 divide-x divide-border text-center">
                    <div>
                      <dt className="text-[12.5px] text-text-3">Consumidas</dt>
                      <dd className="mt-0.5 text-[18px] font-semibold text-text">
                        <AnimatedNumber value={eaten.kcal} />
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[12.5px] text-text-3">Objetivo</dt>
                      <dd className="mt-0.5 text-[18px] font-semibold text-text" data-num>
                        {fmt(targets.kcal)}
                      </dd>
                    </div>
                  </dl>

                  <div className="mt-5 grid grid-cols-3 gap-2.5">
                    {GRAM_MACROS.map((m, i) => {
                      const value = eaten[m.key]
                      const target = targets[m.key]
                      return (
                        <div key={m.key} className="flex flex-col items-center rounded-md bg-surface-2 px-1.5 py-3">
                          <Ring
                            progress={target ? value / target : 0}
                            size={54}
                            stroke={6}
                            color={m.color}
                            overColor={m.color}
                            delay={0.12 + i * 0.08}
                            label={`${m.label}: ${fmt(value)} de ${fmt(target)} gramos`}
                          >
                            <span className="text-[15px] font-bold" style={{ color: m.text }} aria-hidden>
                              {m.letter}
                            </span>
                          </Ring>
                          <span className="mt-2 text-[12px] font-medium text-text-2">{m.short}</span>
                          <span className="mt-0.5 text-[13.5px] font-semibold text-text" aria-hidden>
                            <AnimatedNumber value={value} />
                            <span className="font-medium text-text-3" data-num>
                              {' '}
                              / {fmt(target)} g
                            </span>
                          </span>
                        </div>
                      )
                    })}
                  </div>
                  {(list.length > 0 || day.exercise > 0) && (
                    <p className="mt-3.5 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[13px] text-text-2" data-num>
                      <span className="flex items-center gap-1.5">
                        <Leaf className="size-3.5 text-text-3" aria-hidden />
                        Fibra <strong className="font-semibold text-text">{fmt(extras.fiber)} g</strong>
                        <span className="text-text-3">
                          · orientativo {FIBER_TARGET.min}-{FIBER_TARGET.max} g
                        </span>
                      </span>
                      {day.exercise > 0 && (
                        <span className="flex items-center gap-1.5">
                          <Activity className="size-3.5 text-text-3" aria-hidden />
                          Entreno <strong className="font-semibold text-text">≈ {fmt(day.exercise)} kcal</strong>
                          <span className="text-text-3">· {app.prefs?.add_exercise_kcal ? 'sumadas al objetivo' : 'solo referencia'}</span>
                        </span>
                      )}
                      {extras.alcohol > 0 && (
                        <span className="flex items-center gap-1.5">
                          <Wine className="size-3.5 text-text-3" aria-hidden />
                          Alcohol <strong className="font-semibold text-text">{fmt(extras.alcohol, 1)} g</strong>
                          <span className="text-text-3">· {fmt(extras.alcohol * 7)} kcal</span>
                        </span>
                      )}
                    </p>
                  )}
                </>
              )}
            </section>

            {/* Misma altura que el aviso ya cargado: la lista de comidas no se desplaza al llegar. */}
            {loading && <Skeleton className="mt-3 h-[68px] !rounded-[22px]" />}
            {!loading && (
              <motion.p
                key={tip.text}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={clsx('mt-3 flex items-start gap-3 rounded-lg p-3.5 text-[14.5px] leading-snug text-text', tipStyle.box)}
              >
                <Lightbulb className={clsx('mt-px size-[18px] shrink-0', tipStyle.icon)} aria-hidden />
                {tip.text}
              </motion.p>
            )}
            {!loading && isToday && <SuggestCard date={date} eaten={eaten} targets={targets} meals={list} />}
            {!loading && <WaterCard date={date} />}
          </div>

          <section className="mt-6 lg:mt-0" aria-label="Comidas del día">
            {loading ? (
              <div className="space-y-2.5" role="status" aria-label="Cargando comidas">
                <Skeleton className="h-5 w-28" />
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-[60px]" />
                ))}
              </div>
            ) : groups.length === 0 ? (
              <div className="card">
                <EmptyState
                  art="plate"
                  title={isToday ? 'Aún no has apuntado nada' : 'Día sin registros'}
                  text={
                    isToday
                      ? 'Escríbelo, díctalo o haz una foto. Yo me encargo de los números.'
                      : 'Puedes añadir lo que comiste ese día cuando quieras.'
                  }
                  action={
                    <Button onClick={() => openAddMeal({ date })} icon={<Plus className="size-5" aria-hidden />}>
                      Añadir comida
                    </Button>
                  }
                />
              </div>
            ) : (
              <div className="space-y-5">
                {groups.map((group) => {
                  const subtotal = sumMacros(group.meals)
                  return (
                    <div key={group.key}>
                      <div className="flex items-center justify-between gap-2">
                        <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text">
                          <group.Icon className="size-[17px] text-text-3" aria-hidden />
                          {group.label}
                        </h2>
                        <div className="flex items-center gap-1">
                          <span className="text-[13.5px] font-medium text-text-2" data-num>
                            {fmt(subtotal.kcal)} kcal
                          </span>
                          <button
                            type="button"
                            onClick={() => openAddMeal({ date, slot: group.key })}
                            aria-label={`Añadir a ${group.label.toLowerCase()}`}
                            className="-mr-2.5 grid size-11 place-items-center rounded-full text-text-3 hover:text-accent-text"
                          >
                            <Plus className="size-[18px]" aria-hidden />
                          </button>
                        </div>
                      </div>
                      <ul className="space-y-2">
                        <AnimatePresence>
                          {group.meals.map((meal, index) => (
                            <MealRow key={meal.client_id} meal={meal} index={groupOffset[group.key] + index} onOpen={setDetail} onDelete={remove} />
                          ))}
                        </AnimatePresence>
                      </ul>
                    </div>
                  )
                })}
                <Button variant="ghost" size="sm" block onClick={() => setCopyDay(true)} icon={<CopyPlus className="size-4" aria-hidden />}>
                  Copiar este día a otro
                </Button>
              </div>
            )}
          </section>
        </motion.div>
      </AnimatePresence>

      <MealSheet meal={detail} onClose={() => setDetail(null)} onDelete={remove} />
      <Sheet open={copyDay} onClose={() => setCopyDay(false)} title={`Copiar ${isToday ? 'hoy' : relativeDay(date).toLowerCase()}`}>
        <CopyPanel sourceDate={date} count={list.length} kcal={eaten.kcal} onCopy={copyAll} onCancel={() => setCopyDay(false)} />
      </Sheet>
    </main>
  )
}

import clsx from 'clsx'
import { motion, useReducedMotion } from 'motion/react'
import {
  Beef,
  BookOpen,
  Camera,
  ChevronLeft,
  ChevronRight,
  Flame,
  Lock,
  Mic,
  NotebookPen,
  PiggyBank,
  Scale,
  Star,
  Target,
  TrendingDown,
  TrendingUp,
  Trophy,
  Utensils,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useStats, useSummaries, useWeek } from '@/hooks/data'
import { addDays, fmtRange, fmtWeekday, todayISO, weekdayInitial, weekStart } from '@/lib/dates'
import { capitalize, fmt, fmtSigned, plural } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import type { AchievementInfo, Badge, DayStatus, WeekSummary } from '@/lib/types'
import { AnimatedNumber } from '@/ui/AnimatedNumber'
import { EmptyState } from '@/ui/EmptyState'
import { IconButton } from '@/ui/Button'
import { Ring } from '@/ui/Ring'
import { Skeleton } from '@/ui/Skeleton'

const ACHIEVEMENT_ICONS: Record<string, LucideIcon> = {
  utensils: Utensils,
  notebook: NotebookPen,
  book: BookOpen,
  flame: Flame,
  trophy: Trophy,
  beef: Beef,
  scale: Scale,
  target: Target,
  zap: Zap,
  piggy: PiggyBank,
  star: Star,
  camera: Camera,
  mic: Mic,
}

const BADGE_TONE: Record<Badge['tone'], string> = {
  kcal: 'bg-kcal-soft text-kcal-text',
  protein: 'bg-protein-soft text-protein-text',
  carbs: 'bg-carbs-soft text-carbs-text',
  fat: 'bg-fat-soft text-fat-text',
  neutral: 'bg-surface-2 text-text-2',
}

const BAR_COLOR: Record<DayStatus, string> = {
  cumplido: 'var(--kcal)',
  bajo: 'var(--text-3)',
  pasado: 'var(--kcal-over)',
  sin_registro: 'var(--track)',
}
const STATUS_TEXT: Record<DayStatus, string> = {
  cumplido: 'en objetivo',
  bajo: 'por debajo',
  pasado: 'por encima',
  sin_registro: 'sin registro',
}

function Tile({ label, children, hint, className }: { label: string; children: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <div className={clsx('card p-4', className)}>
      <p className="text-[12.5px] font-medium text-text-2">{label}</p>
      <div className="mt-1.5 text-[26px] leading-none font-semibold tracking-[-0.03em] text-text">{children}</div>
      {hint && <p className="mt-2 text-[12.5px] leading-snug text-text-3">{hint}</p>}
    </div>
  )
}

function Delta({ value, unit, goodWhenNegative }: { value: number; unit: string; goodWhenNegative?: boolean }) {
  if (value === 0) return <span className="text-text-3">igual que la anterior</span>
  const good = goodWhenNegative ? value < 0 : value > 0
  const Icon = value > 0 ? TrendingUp : TrendingDown
  return (
    <span className={clsx('inline-flex items-center gap-1 font-medium', good ? 'text-accent-text' : 'text-text-2')} data-num>
      <Icon className="size-3.5" aria-hidden />
      {fmtSigned(value)} {unit}
    </span>
  )
}

function projectionText(summary: WeekSummary): string {
  const projection = summary.projection
  if (!projection) return 'Sin datos esta semana todavía.'
  if (projection.direction === 'estable' || projection.weeks_per_kg === null) {
    return 'A este ritmo tu peso se mantiene estable.'
  }
  const weeks = projection.weeks_per_kg
  const verb = projection.direction === 'perdida' ? 'perderías' : 'ganarías'
  if (weeks < 1) return `A este ritmo ${verb} ${fmt(Math.abs(projection.weekly_kg), 1)} kg por semana.`
  return `A este ritmo ${verb} 1 kg cada ${fmt(weeks, 1)} ${plural(weeks, 'semana', 'semanas')}.`
}

function WeekBars({ summary }: { summary: WeekSummary }) {
  const reduce = useReducedMotion()
  const target = summary.targets.kcal
  const max = Math.max(target * 1.25, ...summary.days.map((d) => d.kcal))
  const today = todayISO()
  return (
    <div className="relative">
      <ul className="grid h-[112px] grid-cols-7 items-end gap-2">
        {summary.days.map((day, i) => {
          const height = day.logged ? Math.max(6, (day.kcal / max) * 100) : 4
          return (
            <li key={day.date} className="flex h-full flex-col items-center justify-end gap-1.5">
              <div className="flex w-full flex-1 items-end justify-center">
                <motion.div
                  role="img"
                  aria-label={`${capitalize(fmtWeekday(day.date))}: ${day.logged ? `${fmt(day.kcal)} kilocalorías, ${STATUS_TEXT[day.status]}` : 'sin registro'}`}
                  className="w-full max-w-[22px] rounded-t-[4px]"
                  style={{ background: BAR_COLOR[day.status] }}
                  initial={reduce ? false : { height: 0 }}
                  animate={{ height: `${height}%` }}
                  transition={{ duration: 0.6, delay: i * 0.05, ease: [0.22, 1, 0.36, 1] }}
                />
              </div>
              <span className={clsx('text-[11.5px] font-semibold', day.date === today ? 'text-accent-text' : 'text-text-3')} aria-hidden>
                {weekdayInitial(day.date)}
              </span>
            </li>
          )
        })}
      </ul>
      <div
        className="pointer-events-none absolute inset-x-0 border-t border-text-2"
        style={{ bottom: `calc(${(target / max) * (112 - 24)}px + 24px)` }}
        aria-hidden
      >
        <span className="absolute -top-[17px] right-0 text-[11px] text-text-2" data-num>
          Objetivo {fmt(target)}
        </span>
      </div>
    </div>
  )
}

function Achievement({ achievement, index }: { achievement: AchievementInfo; index: number }) {
  const Icon = ACHIEVEMENT_ICONS[achievement.icon] ?? Trophy
  const unlocked = !!achievement.unlocked_at
  return (
    <motion.li
      initial={{ opacity: 0, scale: 0.92 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true, margin: '-20px' }}
      transition={{ delay: (index % 3) * 0.05, duration: 0.3 }}
      className={clsx('card flex flex-col items-center px-2 py-3.5 text-center', !unlocked && 'opacity-55')}
    >
      <span className={clsx('relative grid size-11 place-items-center rounded-full', unlocked ? 'bg-accent-soft text-accent-text' : 'bg-surface-2 text-text-3')}>
        <Icon className="size-5" aria-hidden />
        {!unlocked && (
          <span className="absolute -right-1 -bottom-1 grid size-[18px] place-items-center rounded-full border border-border bg-surface">
            <Lock className="size-2.5" aria-hidden />
          </span>
        )}
      </span>
      <p className="mt-2 text-[12.5px] leading-tight font-semibold text-text">{achievement.title}</p>
      <p className="mt-1 text-[11.5px] leading-snug text-text-3">{achievement.text}</p>
      <span className="sr-only">{unlocked ? 'Logro desbloqueado' : 'Logro bloqueado'}</span>
    </motion.li>
  )
}

export default function Summary() {
  const today = todayISO()
  const currentWeek = weekStart(today)
  const [start, setStart] = useState(currentWeek)
  const week = useWeek(start)
  const stats = useStats()
  const history = useSummaries()
  const summary = week.data
  const isCurrent = start === currentWeek
  const streak = stats.data?.streak

  const shift = (weeks: number) => {
    const next = addDays(start, weeks * 7)
    if (next > currentWeek) return
    haptic('select')
    setStart(next)
  }

  return (
    <main className="page">
      <header className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-[30px] leading-tight font-semibold tracking-[-0.035em] text-text">Resumen</h1>
          <p className="mt-1 text-[14.5px] text-text-2" data-num>
            {isCurrent ? 'Esta semana' : 'Semana del'} · {fmtRange(start, addDays(start, 6))}
          </p>
        </div>
        <div className="flex shrink-0">
          <IconButton label="Semana anterior" onClick={() => shift(-1)}>
            <ChevronLeft className="size-5" aria-hidden />
          </IconButton>
          <IconButton label="Semana siguiente" onClick={() => shift(1)} disabled={isCurrent}>
            <ChevronRight className="size-5" aria-hidden />
          </IconButton>
        </div>
      </header>

      {streak && (
        <section className="card mt-4 flex items-center gap-4 overflow-hidden p-4" aria-label="Racha">
          <motion.div
            animate={streak.current > 0 ? { scale: [1, 1.08, 1], rotate: [0, -3, 3, 0] } : undefined}
            transition={{ duration: 1.8, repeat: Infinity, repeatDelay: 1.6 }}
            className={clsx('grid size-14 shrink-0 place-items-center rounded-full', streak.current > 0 ? 'bg-carbs-soft' : 'bg-surface-2')}
          >
            <Flame className={clsx('size-7', streak.current > 0 ? 'fill-kcal-from text-kcal-from' : 'text-text-3')} aria-hidden />
          </motion.div>
          <div className="min-w-0 flex-1">
            <p className="text-[22px] leading-tight font-semibold tracking-[-0.02em] text-text">
              <AnimatedNumber value={streak.current} /> {plural(streak.current, 'día seguido', 'días seguidos')}
            </p>
            <p className="mt-0.5 text-[13.5px] text-text-2">
              {streak.current === 0
                ? 'Cumple hoy tu objetivo de calorías y empieza la racha.'
                : streak.today_done
                  ? 'Hoy ya está cumplido. Que no decaiga.'
                  : 'Cumple el objetivo de hoy para sumar otro.'}
            </p>
          </div>
          {streak.best > 0 && (
            <div className="shrink-0 text-right">
              <p className="text-[11.5px] text-text-3">Mejor racha</p>
              <p className="text-[17px] font-semibold text-text" data-num>
                {streak.best}
              </p>
            </div>
          )}
        </section>
      )}

      {week.isPending ? (
        <div className="mt-4 space-y-4" role="status" aria-label="Cargando resumen">
          <Skeleton className="h-[190px] !rounded-[22px]" />
          <div className="grid grid-cols-2 gap-3">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-[104px] !rounded-[22px]" />
            ))}
          </div>
        </div>
      ) : !summary || summary.logged_days === 0 ? (
        <div className="card mt-4">
          <EmptyState
            art="chart"
            title={isCurrent ? 'La semana acaba de empezar' : 'Semana sin registros'}
            text={isCurrent ? 'En cuanto apuntes tu primera comida verás aquí cómo va la semana.' : 'No apuntaste nada esos días.'}
          />
        </div>
      ) : (
        <motion.div key={start} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mt-4 space-y-4">
          {summary.badges.length > 0 && (
            <ul className="flex flex-wrap gap-2" aria-label="Insignias de la semana">
              {summary.badges.map((badge, i) => (
                <motion.li
                  key={badge.key}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.1 + i * 0.07, type: 'spring', stiffness: 420, damping: 24 }}
                  className={clsx('inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[13px] font-semibold', BADGE_TONE[badge.tone])}
                >
                  <Trophy className="size-3.5" aria-hidden />
                  {badge.label}
                </motion.li>
              ))}
            </ul>
          )}

          <section className="card p-4" aria-label="Calorías de la semana">
            <div className="flex items-center gap-4">
              <Ring progress={summary.adherence_pct / 100} size={84} stroke={9} color="var(--kcal)" label={`Adherencia del ${summary.adherence_pct} por ciento`}>
                <span className="text-[20px] font-semibold tracking-[-0.02em] text-text">
                  <AnimatedNumber value={summary.adherence_pct} />
                  <span className="text-[12px] text-text-3">%</span>
                </span>
              </Ring>
              <div className="min-w-0">
                <p className="text-[12.5px] font-medium text-text-2">Adherencia</p>
                <p className="mt-0.5 text-[15.5px] leading-snug font-medium text-text">
                  {summary.on_target_days} de {summary.days_elapsed} {plural(summary.days_elapsed, 'día', 'días')} en objetivo
                </p>
                <p className="mt-1 text-[12.5px] text-text-3">Cuenta como cumplido quedarse a ±10 % de las calorías.</p>
              </div>
            </div>
            <div className="mt-6">
              <WeekBars summary={summary} />
            </div>
          </section>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile
              label="Media diaria"
              hint={
                <>
                  Objetivo {fmt(summary.targets.kcal)} · <span data-num>{fmtSigned(summary.avg_kcal - summary.targets.kcal)}</span>
                </>
              }
            >
              <AnimatedNumber value={summary.avg_kcal} />
              <span className="ml-1 text-[13px] font-medium text-text-3">kcal</span>
            </Tile>
            <Tile
              label="Balance total"
              hint={summary.balance_total < 0 ? 'Déficit frente a tu mantenimiento' : summary.balance_total > 0 ? 'Superávit frente a tu mantenimiento' : 'En equilibrio'}
            >
              <AnimatedNumber value={summary.balance_total} format={(n) => fmtSigned(n)} />
              <span className="ml-1 text-[13px] font-medium text-text-3">kcal</span>
            </Tile>
            <Tile label="Días en déficit" hint={`De ${summary.logged_days} ${plural(summary.logged_days, 'registrado', 'registrados')}`}>
              <AnimatedNumber value={summary.deficit_days} />
            </Tile>
            <Tile label="Días pasados de objetivo" hint={summary.over_target_days === 0 ? 'Ninguno por encima del +10 %' : 'Por encima del +10 %'}>
              <AnimatedNumber value={summary.over_target_days} />
            </Tile>
          </div>

          <section className="card flex items-start gap-3.5 p-4" aria-label="Proyección">
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-kcal-soft text-kcal-text">
              {summary.projection?.direction === 'ganancia' ? <TrendingUp className="size-5" aria-hidden /> : <TrendingDown className="size-5" aria-hidden />}
            </span>
            <div className="min-w-0">
              <p className="text-[16px] leading-snug font-semibold tracking-[-0.01em] text-text">{projectionText(summary)}</p>
              <p className="mt-1 text-[13px] leading-snug text-text-3">
                Estimación con ≈ 7.700 kcal por kilo de grasa, a partir del balance medio de los días registrados.
              </p>
            </div>
          </section>

          <div className="grid gap-3 lg:grid-cols-2">
            {summary.best_day && (
              <section className="card divide-y divide-border" aria-label="Mejor y peor día">
                <div className="flex items-center justify-between gap-3 p-4">
                  <div>
                    <p className="text-[12.5px] font-medium text-text-2">Mejor día</p>
                    <p className="mt-0.5 text-[15.5px] font-semibold text-text">{capitalize(fmtWeekday(summary.best_day.date))}</p>
                  </div>
                  <p className="text-right text-[14px] text-text-2" data-num>
                    {fmt(summary.best_day.kcal)} kcal
                    <span className="block text-[12.5px] text-text-3">{fmtSigned(summary.best_day.diff)} frente al objetivo</span>
                  </p>
                </div>
                {summary.worst_day && (
                  <div className="flex items-center justify-between gap-3 p-4">
                    <div>
                      <p className="text-[12.5px] font-medium text-text-2">Día más alejado</p>
                      <p className="mt-0.5 text-[15.5px] font-semibold text-text">{capitalize(fmtWeekday(summary.worst_day.date))}</p>
                    </div>
                    <p className="text-right text-[14px] text-text-2" data-num>
                      {fmt(summary.worst_day.kcal)} kcal
                      <span className="block text-[12.5px] text-text-3">{fmtSigned(summary.worst_day.diff)} frente al objetivo</span>
                    </p>
                  </div>
                )}
              </section>
            )}

            <section className="card divide-y divide-border" aria-label="Proteína y peso">
              <div className="flex items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-[12.5px] font-medium text-text-2">Proteína cumplida</p>
                  <p className="mt-0.5 text-[15.5px] font-semibold text-text" data-num>
                    {summary.protein_days} de {summary.logged_days} {plural(summary.logged_days, 'día', 'días')}
                  </p>
                </div>
                <p className="text-right text-[14px] text-text-2" data-num>
                  {fmt(summary.avg_protein)} g de media
                  <span className="block text-[12.5px] text-text-3">Objetivo {fmt(summary.targets.protein)} g</span>
                </p>
              </div>
              <div className="flex items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-[12.5px] font-medium text-text-2">Tendencia de peso</p>
                  <p className="mt-0.5 text-[15.5px] font-semibold text-text" data-num>
                    {summary.weight.avg === null ? 'Sin pesadas' : `${fmt(summary.weight.avg, 1)} kg de media`}
                  </p>
                </div>
                <p className="text-right text-[13.5px]">
                  {summary.weight.change === null ? (
                    <span className="text-text-3">Pésate esta semana y la anterior para ver la tendencia</span>
                  ) : (
                    <span className="font-medium text-text-2" data-num>
                      {fmtSigned(summary.weight.change, 1)} kg
                      <span className="block text-[12.5px] font-normal text-text-3">frente a la semana anterior</span>
                    </span>
                  )}
                </p>
              </div>
            </section>
          </div>

          {summary.vs_previous && (
            <section className="card p-4" aria-label="Comparación con la semana anterior">
              <h2 className="text-[15px] font-semibold text-text">Frente a la semana anterior</h2>
              <dl className="mt-3 grid grid-cols-1 gap-2.5 text-[14px] sm:grid-cols-3">
                <div className="flex items-center justify-between gap-3 sm:block">
                  <dt className="text-text-2">Adherencia</dt>
                  <dd className="sm:mt-1">
                    <Delta value={summary.vs_previous.adherence_pct} unit="puntos" />
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3 sm:block">
                  <dt className="text-text-2">Media diaria</dt>
                  <dd className="sm:mt-1">
                    <Delta value={summary.vs_previous.avg_kcal} unit="kcal" goodWhenNegative={summary.avg_kcal > summary.targets.kcal} />
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3 sm:block">
                  <dt className="text-text-2">Proteína media</dt>
                  <dd className="sm:mt-1">
                    <Delta value={summary.vs_previous.avg_protein} unit="g" />
                  </dd>
                </div>
              </dl>
            </section>
          )}
        </motion.div>
      )}

      {stats.data && (
        <section className="mt-7" aria-labelledby="s-achievements">
          <div className="flex items-baseline justify-between">
            <h2 id="s-achievements" className="text-[19px] font-semibold tracking-[-0.02em] text-text">
              Logros
            </h2>
            <span className="text-[13.5px] text-text-3" data-num>
              {stats.data.achievements.filter((a) => a.unlocked_at).length} de {stats.data.achievements.length}
            </span>
          </div>
          <ul className="mt-3 grid grid-cols-3 gap-2.5 lg:grid-cols-6">
            {stats.data.achievements.map((achievement, index) => (
              <Achievement key={achievement.key} achievement={achievement} index={index} />
            ))}
          </ul>
        </section>
      )}

      {history.data && history.data.length > 0 && (
        <section className="mt-7" aria-labelledby="s-history">
          <h2 id="s-history" className="text-[19px] font-semibold tracking-[-0.02em] text-text">
            Semanas anteriores
          </h2>
          <ul className="card mt-3 divide-y divide-border overflow-hidden">
            {history.data.map((past) => (
              <li key={past.week_start}>
                <button
                  type="button"
                  onClick={() => {
                    haptic('select')
                    setStart(past.week_start)
                    window.scrollTo({ top: 0, behavior: 'smooth' })
                  }}
                  aria-current={past.week_start === start ? 'true' : undefined}
                  className={clsx('flex min-h-[64px] w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-surface-2', past.week_start === start && 'bg-surface-2')}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-[15px] font-medium text-text" data-num>
                      {fmtRange(past.week_start, past.week_end)}
                    </p>
                    <p className="mt-0.5 text-[12.5px] text-text-3" data-num>
                      {fmt(past.avg_kcal)} kcal de media · {past.logged_days}/7 días
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-[15.5px] font-semibold text-text" data-num>
                      {past.adherence_pct} %
                    </p>
                    <p className="text-[11.5px] text-text-3">adherencia</p>
                  </div>
                  <ChevronRight className="size-4 shrink-0 text-text-3" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}

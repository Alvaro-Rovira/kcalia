import { Droplets } from 'lucide-react'
import { useWaterDays } from '@/hooks/data'
import { addDays, fmtWeekday, weekdayInitial } from '@/lib/dates'
import { capitalize } from '@/lib/format'
import { fmtWater } from '@/lib/water'

/** Agua de la semana: una barra por día frente al objetivo y la media de los días con registro. */
export function WaterWeek({ start }: { start: string }) {
  const end = addDays(start, 6)
  const { data } = useWaterDays(start, end)
  if (!data) return null
  const byDate = new Map(data.days.map((d) => [d.date, d.ml]))
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i))
  const logged = data.days.filter((d) => d.ml > 0)
  const average = logged.length ? logged.reduce((sum, d) => sum + d.ml, 0) / logged.length : 0
  const reached = logged.filter((d) => d.ml >= data.goal_ml).length
  const max = Math.max(data.goal_ml * 1.2, ...data.days.map((d) => d.ml))
  return (
    <section className="card p-4" aria-label="Agua de la semana">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text">
          <Droplets className="size-[17px] text-info-text" aria-hidden />
          Agua
        </h2>
        <p className="text-[13.5px] text-text-2" data-num>
          {logged.length ? `${fmtWater(average)} de media · objetivo ${reached} de ${logged.length}` : 'Sin registros esta semana'}
        </p>
      </div>
      <ul className="mt-3 grid h-[64px] grid-cols-7 items-end gap-2">
        {days.map((day) => {
          const ml = byDate.get(day) ?? 0
          return (
            <li key={day} className="flex h-full flex-col items-center justify-end gap-1">
              <div
                role="img"
                aria-label={`${capitalize(fmtWeekday(day))}: ${ml ? fmtWater(ml) : 'sin registro'}`}
                className={ml >= data.goal_ml ? 'w-full max-w-[18px] rounded-t-[4px] bg-info' : 'w-full max-w-[18px] rounded-t-[4px] bg-info-soft'}
                style={{ height: `${ml ? Math.max(8, (ml / max) * 100) : 4}%` }}
              />
              <span className="text-[11px] font-semibold text-text-3" aria-hidden>
                {weekdayInitial(day)}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

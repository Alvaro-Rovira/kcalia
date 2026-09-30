import { fmt, fmtSigned, plural } from '@/lib/format'
import type { Plan } from '@/lib/types'

interface Props {
  plan: Plan
  targetWeight?: number | null
  className?: string
}

function Row({ step, title, value, text }: { step: number; title: string; value: string; text: string }) {
  return (
    <li className="flex gap-3">
      <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-[12px] font-semibold text-text-2" aria-hidden data-num>
        {step}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-[14.5px] font-medium text-text">{title}</span>
          <span className="shrink-0 text-[14.5px] font-semibold text-text" data-num>
            {value}
          </span>
        </div>
        <p className="mt-0.5 text-[13px] leading-snug text-text-3">{text}</p>
      </div>
    </li>
  )
}

/** Cómo se han calculado los objetivos, paso a paso y sin cajas negras. */
export function PlanExplanation({ plan, targetWeight, className }: Props) {
  const factor = String(plan.activity_factor).replace('.', ',')
  const adjustment = Number(plan.adjustment_pct.toFixed(1))
  const weekly = plan.weekly_kg
  const stable = Math.abs(weekly) < 0.05
  return (
    <section className={`card p-4 ${className ?? ''}`} aria-label="Cómo se ha calculado tu plan">
      <h2 className="text-[15px] font-semibold text-text">Cómo lo he calculado</h2>
      <ol className="mt-3.5 space-y-3.5">
        <Row step={1} title="Metabolismo basal" value={`${fmt(plan.bmr)} kcal`} text="Lo que gastas en reposo, con la fórmula de Mifflin-St Jeor." />
        <Row step={2} title={`× ${factor} por tu actividad`} value={`${fmt(plan.tdee)} kcal`} text="Tus calorías de mantenimiento: con ellas ni subes ni bajas." />
        <Row
          step={3}
          title={adjustment === 0 ? 'Sin ajuste' : `Ajuste del ${fmtSigned(adjustment, Number.isInteger(adjustment) ? 0 : 1)} %`}
          value={`${fmt(plan.kcal)} kcal`}
          text={`${plan.goal_label}: tu objetivo diario.`}
        />
        <Row
          step={4}
          title="Reparto de macros"
          value={`${fmt(plan.protein)} · ${fmt(plan.carbs)} · ${fmt(plan.fat)} g`}
          text={`Proteína a ${String(plan.protein_gkg).replace('.', ',')} g/kg, grasas a ${String(plan.fat_gkg).replace('.', ',')} g/kg y el resto, hidratos.`}
        />
      </ol>
      <p className="mt-4 rounded-md bg-surface-2 p-3 text-[13.5px] leading-relaxed text-text-2">
        {stable ? (
          'Con este plan tu peso debería mantenerse estable.'
        ) : (
          <>
            A este ritmo: <strong className="font-semibold text-text" data-num>{fmtSigned(weekly, 2)} kg por semana</strong> (≈ 7.700 kcal
            por kilo de grasa).
            {plan.weeks_to_target && targetWeight ? (
              <>
                {' '}
                Llegarías a {fmt(targetWeight, Number.isInteger(targetWeight) ? 0 : 1)} kg en unas{' '}
                <strong className="font-semibold text-text" data-num>
                  {plan.weeks_to_target} {plural(plan.weeks_to_target, 'semana', 'semanas')}
                </strong>
                .
              </>
            ) : null}
          </>
        )}
      </p>
    </section>
  )
}

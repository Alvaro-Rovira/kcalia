import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorMessage } from '@/lib/api'
import { fmt } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import type { Expenditure } from '@/lib/types'
import { keys } from '@/offline/queryClient'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { toast } from '@/ui/toast'

const KEY = ['expenditure'] as const

/** Gasto real: el mantenimiento medido con lo que apuntas y tu peso, frente al de la fórmula. */
export function ExpenditureCard() {
  const client = useQueryClient()
  const query = useQuery({ queryKey: KEY, queryFn: () => api.get<Expenditure>('/api/expenditure') })
  const change = useMutation({
    mutationFn: (to: 'apply' | 'formula') => api.post(`/api/expenditure/${to}`),
    onSuccess: (_, to) => {
      haptic('success')
      void client.invalidateQueries({ queryKey: keys.bootstrap })
      void client.invalidateQueries({ queryKey: KEY })
      toast.success(to === 'apply' ? 'Objetivos recalculados con tu gasto real' : 'Objetivos recalculados con la fórmula')
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const data = query.data
  if (!data) return null

  const measuredWith = `Medido con ${data.days} días apuntados y ${data.weighins} pesajes`
  const trend =
    data.slope_kg_week == null ? '' : `; tu peso ${data.slope_kg_week < 0 ? 'baja' : 'sube'} ${fmt(Math.abs(data.slope_kg_week), 2)} kg a la semana`

  return (
    <section aria-labelledby="gasto-real" className="rounded-md border border-border bg-surface p-3.5">
      <h3 id="gasto-real" className="text-[15px] font-semibold text-text">
        Tu gasto real
      </h3>
      {data.status === 'insuficiente' && <p className="mt-1 text-[13.5px] text-text-2">{data.reason} Mientras tanto se usa la fórmula.</p>}
      {data.status === 'dudoso' && (
        <Notice level="warn" className="mt-2">
          {data.reason}
        </Notice>
      )}
      {data.status === 'ok' && data.estimate != null && (
        <>
          <p className="mt-1.5 leading-none" data-num>
            <span className="text-[30px] font-semibold tracking-[-0.03em] text-text">{fmt(data.estimate)}</span>
            <span className="ml-1.5 text-[14px] text-text-3">kcal al día</span>
          </p>
          <p className="mt-1.5 text-[13px] text-text-2">
            La fórmula calcula {fmt(data.formula)} kcal. {measuredWith}
            {trend}.
            {data.weight_factor < 1 ? ' Con más semanas de datos pesará menos la fórmula.' : ''}
          </p>
        </>
      )}
      {data.mode === 'real' && (
        <p className="mt-2 text-[13px] text-text-2">
          Tus objetivos usan tu gasto real ({fmt(data.applied ?? 0)} kcal). Las calorías del entreno no se suman aparte: ya van incluidas.
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {data.status === 'ok' && data.mode === 'formula' && (
          <Button size="sm" onClick={() => change.mutate('apply')} disabled={change.isPending}>
            Usar mi gasto real
          </Button>
        )}
        {data.mode === 'real' && data.suggest_update && data.estimate != null && (
          <Button size="sm" onClick={() => change.mutate('apply')} disabled={change.isPending}>
            Actualizar a {fmt(data.estimate)} kcal
          </Button>
        )}
        {data.mode === 'real' && (
          <Button size="sm" variant="secondary" onClick={() => change.mutate('formula')} disabled={change.isPending}>
            Volver a la fórmula
          </Button>
        )}
      </div>
    </section>
  )
}

import { RotateCcw } from 'lucide-react'
import { useApp, usePrefsActions } from '@/hooks/data'
import { GENERIC } from '@/lib/suggest'
import { Stepper } from '@/ui/Field'
import { Switch } from '@/ui/Switch'

/** Ajustes de la sugerencia para cerrar el día: activarla, desde cuándo y qué se ha ocultado. */
export function SuggestSettings() {
  const app = useApp()
  const save = usePrefsActions()
  const prefs = app.prefs ?? { water_goal_ml: null }
  const enabled = prefs.suggest_enabled !== false
  const min = prefs.suggest_min_kcal ?? app.suggest_min_kcal_default ?? 80
  const hidden = prefs.suggest_hidden ?? []

  function nameOf(key: string): string {
    const [kind, id] = [key.slice(0, key.indexOf(':')), key.slice(key.indexOf(':') + 1)]
    if (kind === 'dish') return app.dishes.find((d) => String(d.id) === id)?.name ?? 'Comida que ya no está'
    if (kind === 'product') {
      const product = app.products.find((p) => String(p.id) === id)
      return product ? product.alias || product.name : 'Producto que ya no está'
    }
    if (kind === 'generic') return GENERIC.find((g) => g.key === key)?.name ?? id
    return id
  }

  return (
    <>
      <Switch
        label="Sugerir cómo cerrar el día"
        description="Con lo que ya comes, sin pasarte de tus calorías. Aparece si hay cena apuntada, a partir de la hora elegida o al tocar «Ya terminé de comer»."
        checked={enabled}
        onChange={(on) => save({ suggest_enabled: on })}
      />
      {enabled && (
        <>
          <div className="border-t border-border px-4 py-3">
            <p className="mb-2 text-[14px] text-text">Solo si quedan al menos</p>
            <Stepper label="Calorías mínimas" value={min} onChange={(value) => save({ suggest_min_kcal: value })} step={10} min={20} max={500} unit="kcal" />
          </div>
          <label className="flex min-h-[52px] items-center justify-between gap-3 border-t border-border px-4 py-2">
            <span className="text-[15px] text-text">A partir de las</span>
            <input
              type="time"
              value={prefs.suggest_hour ?? '21:00'}
              onChange={(e) => e.target.value && save({ suggest_hour: e.target.value })}
              aria-label="Hora a partir de la que aparece la sugerencia"
              className="h-11 rounded-sm border border-border bg-surface-2 px-2.5 text-[15px] text-text"
            />
          </label>
          {hidden.length > 0 && (
            <div className="border-t border-border px-4 py-3">
              <p className="text-[13px] font-medium text-text-2">Ocultadas ({hidden.length})</p>
              <ul className="mt-1">
                {hidden.map((key) => (
                  <li key={key} className="flex min-h-11 items-center justify-between gap-3">
                    <span className="min-w-0 truncate text-[14px] text-text">{nameOf(key)}</span>
                    <button
                      type="button"
                      onClick={() => save({ suggest_hidden: hidden.filter((k) => k !== key) })}
                      className="inline-flex min-h-11 shrink-0 items-center gap-1 px-2 text-[13.5px] font-medium text-accent-text"
                    >
                      <RotateCcw className="size-3.5" aria-hidden /> Restaurar
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      <p className="border-t border-border px-4 py-2.5 text-[12.5px] text-text-3">Son orientaciones generales, no consejo médico.</p>
    </>
  )
}

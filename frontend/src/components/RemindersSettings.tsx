import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { BellOff, BellRing, Send } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useApp, usePrefsActions } from '@/hooks/data'
import { isIOS, isStandalone } from '@/hooks/useInstall'
import { api, errorMessage } from '@/lib/api'
import { haptic } from '@/lib/haptics'
import { currentSubscription, disablePush, enablePush, pushSupported, type PushStatus } from '@/lib/push'
import { SLOT_BY_KEY } from '@/lib/slots'
import type { MealReminder } from '@/lib/types'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { Switch } from '@/ui/Switch'
import { toast } from '@/ui/toast'

const WEEKDAYS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
const WEEKDAY_NAMES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
const DEFAULT_MEALS: MealReminder[] = [
  { slot: 'desayuno', time: '10:30', enabled: true },
  { slot: 'comida', time: '16:00', enabled: true },
  { slot: 'cena', time: '22:15', enabled: true },
]

/** Recordatorios por notificación: activar este dispositivo y elegir a qué hora avisar. */
export function RemindersSettings() {
  const app = useApp()
  const client = useQueryClient()
  const save = usePrefsActions()
  const status = useQuery({ queryKey: ['push'], queryFn: () => api.get<PushStatus>('/api/push'), staleTime: 60_000 })
  const [subscribed, setSubscribed] = useState<boolean | null>(null)
  const [busy, setBusy] = useState(false)
  const prefs = app.prefs ?? { water_goal_ml: null }
  const meals = prefs.meal_reminders ?? DEFAULT_MEALS
  const weighDays = prefs.weigh_days ?? [0, 1, 2, 3, 4, 5, 6]
  const iosBrowser = isIOS() && !isStandalone()
  const denied = pushSupported() && Notification.permission === 'denied'

  useEffect(() => {
    void currentSubscription().then((sub) => setSubscribed(!!sub))
  }, [])

  async function activate() {
    if (!status.data?.public_key) return
    setBusy(true)
    try {
      const result = await enablePush(status.data.public_key)
      if (result === 'ok') {
        setSubscribed(true)
        if (!prefs.reminders) save({ reminders: true })
        haptic('success')
        toast.success('Avisos activados en este dispositivo')
        void client.invalidateQueries({ queryKey: ['push'] })
      } else if (result === 'denied') {
        toast.error('Sin permiso para avisar', 'Actívalo en los ajustes del navegador para este sitio.')
      } else {
        toast.error('Este navegador no admite notificaciones')
      }
    } catch (error) {
      toast.error('No se han podido activar', errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  async function deactivate() {
    setBusy(true)
    try {
      await disablePush()
      setSubscribed(false)
      toast.success('Avisos desactivados en este dispositivo')
      void client.invalidateQueries({ queryKey: ['push'] })
    } catch (error) {
      toast.error('No se han podido desactivar', errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  async function test() {
    try {
      const { sent } = await api.post<{ sent: number }>('/api/push/test')
      toast.success(sent ? 'Aviso de prueba enviado' : 'No hay ningún dispositivo que lo reciba')
    } catch (error) {
      toast.error('No se ha podido enviar', errorMessage(error))
    }
  }

  const setMeal = (index: number, change: Partial<MealReminder>) => save({ meal_reminders: meals.map((m, i) => (i === index ? { ...m, ...change } : m)) })

  return (
    <>
      <div className="space-y-2.5 p-4">
        {status.data && !status.data.configured ? (
          <Notice level="info">Las notificaciones no están configuradas en este servidor (faltan las claves VAPID).</Notice>
        ) : iosBrowser ? (
          <Notice level="info">En iPhone y iPad los avisos solo funcionan con Kcalia instalada en la pantalla de inicio (iOS 16.4 o posterior). Instálala y actívalos desde ella.</Notice>
        ) : !pushSupported() ? (
          <Notice level="info">Este navegador no admite notificaciones.</Notice>
        ) : denied ? (
          <Notice level="warn">Has bloqueado las notificaciones de este sitio. Permítelas en los ajustes del navegador para recibir avisos.</Notice>
        ) : subscribed ? (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={() => void test()} icon={<Send className="size-4" aria-hidden />}>
              Enviar un aviso de prueba
            </Button>
            <Button variant="ghost" size="sm" loading={busy} onClick={() => void deactivate()} icon={<BellOff className="size-4" aria-hidden />}>
              Desactivar aquí
            </Button>
          </div>
        ) : (
          <Button block loading={busy} disabled={!status.data?.configured} onClick={() => void activate()} icon={<BellRing className="size-5" aria-hidden />}>
            Activar avisos en este dispositivo
          </Button>
        )}
        {app.user.is_admin && <p className="text-[12.5px] text-text-3">Como administrador, también te avisaré cuando alguien solicite una cuenta.</p>}
      </div>

      <div className="border-t border-border">
        <Switch
          label="Recordatorios"
          description="Solo si a esa hora aún no has apuntado nada de ese momento. Un aviso como mucho por franja y día."
          checked={!!prefs.reminders}
          onChange={(on) => save({ reminders: on })}
        />
      </div>
      {prefs.reminders && (
        <>
          {meals.map((meal, index) => (
            <div key={meal.slot} className="flex min-h-[52px] items-center gap-3 border-t border-border px-4 py-2">
              <label className="flex flex-1 items-center gap-2.5 text-[15px] text-text">
                <input type="checkbox" checked={meal.enabled} onChange={(e) => setMeal(index, { enabled: e.target.checked })} className="size-5 accent-[var(--accent)]" />
                Apuntar {SLOT_BY_KEY[meal.slot].label.toLowerCase()}
              </label>
              <input
                type="time"
                value={meal.time}
                onChange={(e) => e.target.value && setMeal(index, { time: e.target.value })}
                aria-label={`Hora del aviso de ${SLOT_BY_KEY[meal.slot].label.toLowerCase()}`}
                className="h-11 rounded-sm border border-border bg-surface-2 px-2.5 text-[15px] text-text"
              />
            </div>
          ))}
          <div className="border-t border-border px-4 py-3">
            <div className="flex items-center gap-3">
              <label className="flex flex-1 items-center gap-2.5 text-[15px] text-text">
                <input
                  type="checkbox"
                  checked={!!prefs.weigh_reminder}
                  onChange={(e) => save({ weigh_reminder: e.target.checked ? '08:30' : null })}
                  className="size-5 accent-[var(--accent)]"
                />
                Pesarme
              </label>
              {prefs.weigh_reminder && (
                <input
                  type="time"
                  value={prefs.weigh_reminder}
                  onChange={(e) => e.target.value && save({ weigh_reminder: e.target.value })}
                  aria-label="Hora del aviso para pesarse"
                  className="h-11 rounded-sm border border-border bg-surface-2 px-2.5 text-[15px] text-text"
                />
              )}
            </div>
            {prefs.weigh_reminder && (
              <div role="group" aria-label="Días para pesarse" className="mt-2.5 grid grid-cols-7 gap-1.5">
                {WEEKDAYS.map((letter, index) => {
                  const on = weighDays.includes(index)
                  return (
                    <button
                      key={letter}
                      type="button"
                      aria-pressed={on}
                      aria-label={WEEKDAY_NAMES[index]}
                      onClick={() => save({ weigh_days: on ? weighDays.filter((d) => d !== index) : [...weighDays, index].sort() })}
                      className={clsx('h-10 rounded-sm border text-[14px] font-semibold', on ? 'border-accent bg-accent-soft text-accent-text' : 'border-border bg-surface-2 text-text-3')}
                    >
                      {letter}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}
    </>
  )
}

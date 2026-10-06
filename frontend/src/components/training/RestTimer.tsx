import { AnimatePresence, motion } from 'motion/react'
import { Timer, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { haptic } from '@/lib/haptics'
import { fmtElapsed } from '@/lib/training'

const PRESETS = [60, 90, 120, 180]

interface Props {
  /** Momento (ms) en que acaba el descanso, o null si no hay descanso en marcha. */
  endsAt: number | null
  seconds: number
  onChange: (endsAt: number | null) => void
  onSeconds: (seconds: number) => void
}

/** Cuenta atrás de descanso entre series, sobre la barra inferior. Sigue bien aunque la app pase a segundo plano. */
export function RestTimer({ endsAt, seconds, onChange, onSeconds }: Props) {
  const [now, setNow] = useState(Date.now())
  const [choosing, setChoosing] = useState(false)
  const remaining = endsAt ? endsAt - now : 0

  useEffect(() => {
    if (!endsAt) return
    const timer = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(timer)
  }, [endsAt])

  useEffect(() => {
    if (endsAt && remaining <= 0) {
      haptic('success')
      navigator.vibrate?.([120, 80, 120])
      onChange(null)
    }
  }, [endsAt, remaining, onChange])

  return (
    <AnimatePresence>
      {endsAt && remaining > 0 && (
        <motion.div
          role="timer"
          aria-live="off"
          aria-label={`Descanso: quedan ${Math.ceil(remaining / 1000)} segundos`}
          initial={{ y: 24, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 24, opacity: 0 }}
          className="glass fixed inset-x-3 z-40 mx-auto max-w-[520px] rounded-lg p-2.5 shadow-lg lg:bottom-6"
          style={{ bottom: 'calc(var(--nav-h) + var(--safe-b) + 12px)' }}
        >
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setChoosing((v) => !v)} aria-expanded={choosing} className="flex min-h-11 flex-1 items-center gap-2 rounded-md px-2 text-left">
              <Timer className="size-5 text-accent-text" aria-hidden />
              <span className="text-[13px] text-text-2">Descanso</span>
              <span className="text-[22px] font-semibold tracking-[-0.02em] text-text" data-num>
                {fmtElapsed(remaining + 999)}
              </span>
            </button>
            <button type="button" onClick={() => onChange((endsAt ?? Date.now()) - 15_000)} className="h-11 rounded-full border border-border bg-surface-2 px-3 text-[14px] font-semibold text-text" aria-label="15 segundos menos">
              −15
            </button>
            <button type="button" onClick={() => onChange((endsAt ?? Date.now()) + 15_000)} className="h-11 rounded-full border border-border bg-surface-2 px-3 text-[14px] font-semibold text-text" aria-label="15 segundos más">
              +15
            </button>
            <button type="button" onClick={() => onChange(null)} className="grid size-11 place-items-center rounded-full text-text-2" aria-label="Saltar el descanso">
              <X className="size-5" aria-hidden />
            </button>
          </div>
          {choosing && (
            <div role="radiogroup" aria-label="Duración del descanso" className="mt-2 grid grid-cols-4 gap-1.5">
              {PRESETS.map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={seconds === value}
                  onClick={() => {
                    onSeconds(value)
                    onChange(Date.now() + value * 1000)
                    setChoosing(false)
                  }}
                  className={`h-10 rounded-sm border text-[14px] font-semibold ${seconds === value ? 'border-accent bg-accent-soft text-accent-text' : 'border-border bg-surface-2 text-text-2'}`}
                >
                  {fmtElapsed(value * 1000)}
                </button>
              ))}
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

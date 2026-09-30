import { AnimatePresence, motion } from 'motion/react'
import { AlertCircle, CheckCircle2, Info, WifiOff, X } from 'lucide-react'
import { useSyncExternalStore } from 'react'
import { haptic } from '@/lib/haptics'

type Tone = 'success' | 'error' | 'info' | 'offline'

export interface ToastOptions {
  title: string
  description?: string
  tone?: Tone
  /** Acción en el propio aviso, p. ej. "Deshacer". */
  action?: { label: string; onClick: () => void }
  duration?: number
}

interface ToastItem extends ToastOptions {
  id: number
  tone: Tone
}

let items: ToastItem[] = []
let nextId = 1
const listeners = new Set<() => void>()
const timers = new Map<number, ReturnType<typeof setTimeout>>()

function emit(): void {
  for (const listener of listeners) listener()
}

function dismiss(id: number): void {
  const timer = timers.get(id)
  if (timer) clearTimeout(timer)
  timers.delete(id)
  items = items.filter((t) => t.id !== id)
  emit()
}

export function toast(options: ToastOptions): number {
  const id = nextId++
  const tone = options.tone ?? 'info'
  // Como mucho dos a la vez: el más nuevo desplaza al más antiguo.
  for (const old of items.slice(0, Math.max(0, items.length - 1))) dismiss(old.id)
  items = [...items, { ...options, id, tone }]
  emit()
  if (tone === 'error') haptic('error')
  const duration = options.duration ?? (options.action ? 6000 : tone === 'error' ? 5500 : 3200)
  timers.set(
    id,
    setTimeout(() => dismiss(id), duration),
  )
  return id
}

toast.success = (title: string, description?: string) => toast({ title, description, tone: 'success' })
toast.error = (title: string, description?: string) => toast({ title, description, tone: 'error' })
toast.dismiss = dismiss

const ICONS = { success: CheckCircle2, error: AlertCircle, info: Info, offline: WifiOff }
const COLORS: Record<Tone, string> = {
  success: 'text-accent-text',
  error: 'text-danger-text',
  info: 'text-info-text',
  offline: 'text-warn-text',
}

export function Toaster() {
  const list = useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => items,
  )
  return (
    <div
      className="pointer-events-none fixed inset-x-0 z-[70] flex flex-col items-center gap-2 px-4 lg:bottom-8"
      style={{ bottom: 'calc(var(--nav-h) + var(--safe-b) + 84px)' }}
    >
      <AnimatePresence initial={false}>
        {list.map((item) => {
          const Icon = ICONS[item.tone]
          return (
            <motion.div
              key={item.id}
              layout
              role={item.tone === 'error' ? 'alert' : 'status'}
              aria-live={item.tone === 'error' ? 'assertive' : 'polite'}
              initial={{ opacity: 0, y: 24, scale: 0.94 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.96, transition: { duration: 0.16 } }}
              transition={{ type: 'spring', stiffness: 460, damping: 34 }}
              className="glass pointer-events-auto flex w-full max-w-[420px] items-center gap-3 rounded-lg py-2.5 pr-2 pl-3.5 shadow-lg"
            >
              <Icon className={`size-5 shrink-0 ${COLORS[item.tone]}`} aria-hidden />
              <div className="min-w-0 flex-1 py-0.5">
                <p className="text-[14.5px] leading-snug font-medium text-text">{item.title}</p>
                {item.description && <p className="mt-0.5 text-[13px] leading-snug text-text-2">{item.description}</p>}
              </div>
              {item.action ? (
                <button
                  type="button"
                  onClick={() => {
                    haptic('select')
                    item.action?.onClick()
                    dismiss(item.id)
                  }}
                  className="min-h-11 shrink-0 rounded-sm px-3 text-[14px] font-semibold text-accent-text active:opacity-70"
                >
                  {item.action.label}
                </button>
              ) : (
                <button
                  type="button"
                  aria-label="Cerrar aviso"
                  onClick={() => dismiss(item.id)}
                  className="grid size-11 shrink-0 place-items-center rounded-sm text-text-3 active:opacity-70"
                >
                  <X className="size-4" aria-hidden />
                </button>
              )}
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}

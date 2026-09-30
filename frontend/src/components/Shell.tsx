import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { CalendarDays, ChartColumn, CloudOff, House, Plus, Scale, Settings, type LucideIcon } from 'lucide-react'
import { createContext, lazy, Suspense, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { NavLink, useLocation, useNavigate, useSearchParams } from 'react-router'
import { useOnline, usePendingCount } from '@/hooks/data'
import { isValidISO, todayISO } from '@/lib/dates'
import { plural } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import type { Slot } from '@/lib/types'
import { Confetti } from '@/ui/Confetti'
import { Logo, Wordmark } from './Logo'

const AddMealSheet = lazy(() => import('./AddMealSheet'))

interface AddMealOptions {
  date?: string
  slot?: Slot
}

interface ShellContext {
  openAddMeal: (options?: AddMealOptions) => void
  celebrate: () => void
}

const Context = createContext<ShellContext>({ openAddMeal: () => undefined, celebrate: () => undefined })
export const useShell = () => useContext(Context)

const NAV: { to: string; label: string; Icon: LucideIcon }[] = [
  { to: '/', label: 'Hoy', Icon: House },
  { to: '/historial', label: 'Historial', Icon: CalendarDays },
  { to: '/resumen', label: 'Resumen', Icon: ChartColumn },
  { to: '/peso', label: 'Peso', Icon: Scale },
  { to: '/ajustes', label: 'Ajustes', Icon: Settings },
]

function OfflineChip() {
  const online = useOnline()
  const pending = usePendingCount()
  const visible = !online || pending > 0
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          role="status"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -16 }}
          className="pointer-events-none fixed inset-x-0 top-0 z-40 flex justify-center"
          style={{ paddingTop: 'calc(var(--safe-t) + 8px)' }}
        >
          <div className="glass flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[12.5px] font-medium text-text-2 shadow-md">
            <CloudOff className="size-3.5 text-warn-text" aria-hidden />
            {online
              ? `Sincronizando ${pending} ${plural(pending, 'cambio', 'cambios')}…`
              : pending > 0
                ? `Sin conexión · ${pending} ${plural(pending, 'cambio pendiente', 'cambios pendientes')}`
                : 'Sin conexión · viendo lo guardado'}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function BottomNav() {
  return (
    <nav
      aria-label="Principal"
      className="glass fixed inset-x-0 bottom-0 z-30 border-x-0 border-b-0 lg:hidden"
      style={{ paddingBottom: 'var(--safe-b)' }}
    >
      <ul className="mx-auto grid h-[var(--nav-h)] max-w-[520px] grid-cols-5 px-1.5">
        {NAV.map(({ to, label, Icon }) => (
          <li key={to} className="min-w-0">
            <NavLink
              to={to}
              end={to === '/'}
              onClick={() => haptic('tap')}
              className="relative flex h-full flex-col items-center justify-center gap-1 rounded-md"
            >
              {({ isActive }) => (
                <>
                  <span className="relative grid h-8 w-14 place-items-center">
                    {isActive && (
                      <motion.span
                        layoutId="nav-pill"
                        className="absolute inset-0 rounded-full bg-accent-soft"
                        transition={{ type: 'spring', stiffness: 480, damping: 36 }}
                      />
                    )}
                    <motion.span
                      animate={isActive ? { scale: [1, 1.22, 1], y: [0, -2, 0] } : { scale: 1, y: 0 }}
                      transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
                      className="relative"
                    >
                      <Icon
                        className={clsx('size-[22px] transition-colors', isActive ? 'text-accent-text' : 'text-text-3')}
                        strokeWidth={isActive ? 2.4 : 2}
                        aria-hidden
                      />
                    </motion.span>
                  </span>
                  <span className={clsx('text-[11px] leading-none font-medium transition-colors', isActive ? 'text-text' : 'text-text-3')}>
                    {label}
                  </span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function Sidebar({ onAdd }: { onAdd: () => void }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] flex-col border-r border-border bg-surface/60 px-4 py-7 backdrop-blur-xl lg:flex">
      <div className="flex items-center gap-2.5 px-2">
        <Logo size={34} />
        <Wordmark className="text-[23px]" />
      </div>
      <button
        type="button"
        onClick={onAdd}
        className="mt-8 flex h-12 items-center justify-center gap-2 rounded-md bg-accent text-[15px] font-semibold text-on-accent shadow-md transition-colors hover:bg-accent-strong"
      >
        <Plus className="size-5" aria-hidden />
        Añadir comida
      </button>
      <nav aria-label="Principal" className="mt-6">
        <ul className="space-y-1">
          {NAV.map(({ to, label, Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  clsx(
                    'flex h-11 items-center gap-3 rounded-md px-3 text-[15px] font-medium transition-colors',
                    isActive ? 'bg-accent-soft text-text' : 'text-text-2 hover:bg-surface-2 hover:text-text',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className={clsx('size-5', isActive && 'text-accent-text')} aria-hidden />
                    {label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}

function PageFallback() {
  return (
    <div className="page" role="status" aria-label="Cargando">
      <div className="skeleton h-8 w-40" />
      <div className="skeleton mt-6 h-52 !rounded-[22px]" />
      <div className="skeleton mt-4 h-32 !rounded-[22px]" />
    </div>
  )
}

export function Shell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [sheet, setSheet] = useState<{ open: boolean; date: string; slot?: Slot }>({ open: false, date: todayISO() })
  const [confetti, setConfetti] = useState(0)

  const viewedDate = location.pathname === '/' && isValidISO(params.get('fecha')) ? params.get('fecha')! : todayISO()

  const openAddMeal = useCallback(
    (options?: AddMealOptions) => {
      haptic('tap')
      setSheet({ open: true, date: options?.date ?? viewedDate, slot: options?.slot })
    },
    [viewedDate],
  )
  const celebrate = useCallback(() => {
    haptic('success')
    setConfetti((n) => n + 1)
  }, [])
  const value = useMemo(() => ({ openAddMeal, celebrate }), [openAddMeal, celebrate])

  // Cada pantalla empieza arriba, venga de donde venga.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  // Atajo de la PWA instalada: /?nueva=1 abre directamente la hoja de añadir.
  useEffect(() => {
    if (params.get('nueva') !== '1') return
    const next = new URLSearchParams(params)
    next.delete('nueva')
    setParams(next, { replace: true })
    setSheet({ open: true, date: todayISO() })
  }, [params, setParams])

  return (
    <Context.Provider value={value}>
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[90] focus:rounded-md focus:bg-accent focus:px-4 focus:py-2.5 focus:text-on-accent"
      >
        Saltar al contenido
      </a>
      <OfflineChip />
      <Sidebar onAdd={() => openAddMeal()} />
      <div id="contenido" className="lg:pl-[248px]">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.1 } }}
            transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
          >
            <Suspense fallback={<PageFallback />}>{children}</Suspense>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* El contenido se desvanece al pasar bajo el botón flotante en vez de chocar con él. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-x-0 z-20 h-28 lg:hidden"
        style={{
          bottom: 'calc(var(--nav-h) + var(--safe-b))',
          background: 'linear-gradient(to top, var(--bg) 18%, transparent)',
        }}
      />
      <motion.button
        type="button"
        aria-label="Añadir comida"
        onClick={() => openAddMeal()}
        whileTap={{ scale: 0.9 }}
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 420, damping: 26, delay: 0.15 }}
        className="fixed left-1/2 z-30 -ml-7 grid size-14 place-items-center rounded-full bg-accent text-on-accent lg:hidden"
        style={{ bottom: 'calc(var(--nav-h) + var(--safe-b) + 14px)', boxShadow: 'var(--elev-fab)' }}
      >
        <Plus className="size-7" strokeWidth={2.6} aria-hidden />
      </motion.button>

      <BottomNav />
      <Suspense fallback={null}>
        {/* Se carga en segundo plano al arrancar: al pulsar "+" ya está lista. */}
        <AddMealSheet
          open={sheet.open}
          date={sheet.date}
          slot={sheet.slot}
          onClose={() => setSheet((s) => ({ ...s, open: false }))}
          onSaved={(date) => {
            if (location.pathname !== '/' || date !== viewedDate) navigate(date === todayISO() ? '/' : `/?fecha=${date}`)
          }}
        />
      </Suspense>
      <Confetti run={confetti} />
    </Context.Provider>
  )
}

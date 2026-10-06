import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import { CalendarDays, ChartColumn, ClipboardList, CloudOff, Dumbbell, House, Plus, Scale, Settings, ShieldCheck, type LucideIcon } from 'lucide-react'
import { createContext, lazy, Suspense, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { NavLink, useLocation, useNavigate, useSearchParams, type Location } from 'react-router'
import { useAdminOverview } from '@/hooks/admin'
import { useBootstrap, useOnline, usePendingCount, useWaterActions } from '@/hooks/data'
import { isValidISO, todayISO } from '@/lib/dates'
import { plural } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { readShortcut, withoutShortcut } from '@/lib/shortcuts'
import type { Product, Slot } from '@/lib/types'
import { fmtWater } from '@/lib/water'
import { Confetti } from '@/ui/Confetti'
import { toast } from '@/ui/toast'
import { Logo, Wordmark } from './Logo'

const AddMealSheet = lazy(() => import('./AddMealSheet'))
const ProductSheet = lazy(() => import('./ProductSheet'))

interface AddMealOptions {
  date?: string
  slot?: Slot
  /** Texto ya escrito (atajo de voz de iPhone: /?nueva=1&texto=...). */
  text?: string
}

interface ShellContext {
  openAddMeal: (options?: AddMealOptions) => void
  /** Guardar un producto nuevo desde la foto de su etiqueta, o editar uno existente. */
  openProduct: (product?: Product | null) => void
  celebrate: () => void
}

const Context = createContext<ShellContext>({ openAddMeal: () => undefined, openProduct: () => undefined, celebrate: () => undefined })
export const useShell = () => useContext(Context)

interface NavItem {
  to: string
  label: string
  Icon: LucideIcon
  /** Otras rutas en las que esta pestaña cuenta como activa. */
  also?: string[]
}

// En el móvil, cinco pestañas: «Progreso» agrupa el resumen semanal y el cuerpo (peso, medidas y fotos).
const NAV: NavItem[] = [
  { to: '/', label: 'Hoy', Icon: House },
  { to: '/historial', label: 'Historial', Icon: CalendarDays, also: ['/plan'] },
  { to: '/entreno', label: 'Entreno', Icon: Dumbbell },
  { to: '/resumen', label: 'Progreso', Icon: ChartColumn, also: ['/peso'] },
  { to: '/ajustes', label: 'Ajustes', Icon: Settings, also: ['/admin'] },
]

// En el escritorio hay sitio para todo.
const SIDEBAR: NavItem[] = [
  { to: '/', label: 'Hoy', Icon: House },
  { to: '/historial', label: 'Historial', Icon: CalendarDays },
  { to: '/plan', label: 'Plan semanal', Icon: ClipboardList },
  { to: '/entreno', label: 'Entreno', Icon: Dumbbell },
  { to: '/resumen', label: 'Resumen', Icon: ChartColumn },
  { to: '/peso', label: 'Cuerpo', Icon: Scale },
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

/** Solicitudes de cuenta pendientes (solo para el administrador; 0 para el resto). */
function usePendingRequests(): number {
  const { data } = useBootstrap()
  const admin = !!data?.user.is_admin
  return useAdminOverview(admin).data?.pending ?? 0
}

function Badge({ count, className }: { count: number; className?: string }) {
  if (!count) return null
  return (
    <span
      className={clsx('grid h-[18px] min-w-[18px] place-items-center rounded-full bg-danger px-1 text-[11px] leading-none font-bold text-bg', className)}
      data-num
    >
      {count > 9 ? '9+' : count}
      <span className="sr-only"> {count === 1 ? 'solicitud pendiente' : 'solicitudes pendientes'}</span>
    </span>
  )
}

function BottomNav() {
  const requests = usePendingRequests()
  const { pathname } = useLocation()
  return (
    <nav
      aria-label="Principal"
      className="glass fixed inset-x-0 bottom-0 z-30 border-x-0 border-b-0 lg:hidden"
      style={{ paddingBottom: 'var(--safe-b)' }}
    >
      <ul className="mx-auto grid h-[var(--nav-h)] max-w-[520px] grid-cols-5 px-1.5">
        {NAV.map(({ to, label, Icon, also }) => (
          <li key={to} className="min-w-0">
            <NavLink
              to={to}
              end={to === '/'}
              onClick={() => haptic('tap')}
              className="relative flex h-full flex-col items-center justify-center gap-1 rounded-md"
            >
              {({ isActive: exact }) => {
                const isActive = exact || !!also?.some((path) => pathname.startsWith(path))
                return (
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
                    {to === '/ajustes' && <Badge count={requests} className="absolute -top-1 right-1.5" />}
                  </span>
                  <span className={clsx('text-[11px] leading-none font-medium transition-colors', isActive ? 'text-text' : 'text-text-3')}>
                    {label}
                  </span>
                </>
                )
              }}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function Sidebar({ onAdd }: { onAdd: () => void }) {
  const { data } = useBootstrap()
  const requests = usePendingRequests()
  const items = data?.user.is_admin ? [...SIDEBAR, { to: '/admin', label: 'Administración', Icon: ShieldCheck }] : SIDEBAR
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
          {items.map(({ to, label, Icon }) => (
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
                    <span className="flex-1">{label}</span>
                    {to === '/admin' && <Badge count={requests} />}
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

/**
 * `children` recibe la ubicación de su propio contenedor. Mientras una página sale con su animación,
 * su <Routes> debe seguir en la ruta antigua: si leyera la nueva, la página nueva se montaría dos
 * veces (una dentro del contenedor que sale y otra en el que entra).
 */
export function Shell({ children }: { children: (location: Location) => ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [sheet, setSheet] = useState<{ open: boolean; date: string; slot?: Slot; text?: string }>({ open: false, date: todayISO() })
  const [confetti, setConfetti] = useState(0)
  const [productSheet, setProductSheet] = useState<{ open: boolean; product: Product | null }>({ open: false, product: null })
  const [productEver, setProductEver] = useState(false)
  // La hoja de añadir comida se descarga en un momento ocioso: no compite con el primer contenido.
  const [sheetReady, setSheetReady] = useState(false)
  useEffect(() => {
    // Safari (iOS) no tiene requestIdleCallback: se cae a un temporizador corto.
    const hasIdle = 'requestIdleCallback' in window
    const handle = hasIdle
      ? window.requestIdleCallback(() => setSheetReady(true), { timeout: 2500 })
      : window.setTimeout(() => setSheetReady(true), 1200)
    return () => (hasIdle ? window.cancelIdleCallback(handle) : window.clearTimeout(handle))
  }, [])

  const viewedDate = location.pathname === '/' && isValidISO(params.get('fecha')) ? params.get('fecha')! : todayISO()

  const openAddMeal = useCallback(
    (options?: AddMealOptions) => {
      haptic('tap')
      setSheet({ open: true, date: options?.date ?? viewedDate, slot: options?.slot })
    },
    [viewedDate],
  )
  const openProduct = useCallback((product?: Product | null) => {
    haptic('tap')
    setProductEver(true)
    setProductSheet({ open: true, product: product ?? null })
  }, [])
  const celebrate = useCallback(() => {
    haptic('success')
    setConfetti((n) => n + 1)
  }, [])
  const value = useMemo(() => ({ openAddMeal, openProduct, celebrate }), [openAddMeal, openProduct, celebrate])

  // Cada pantalla empieza arriba, venga de donde venga.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  // Atajos de la PWA instalada y del atajo de voz de iPhone:
  // /?nueva=1 abre la hoja de añadir (con &texto=... ya escrito, sin analizar: no se gasta IA desde un enlace)
  // y /?agua=250 apunta un vaso de agua hoy, con «Deshacer».
  const { add: addWater, remove: removeWater } = useWaterActions()
  // Una sola vez por navegación (StrictMode monta los efectos dos veces y el agua se apuntaría doble).
  const handled = useRef<string | null>(null)
  useEffect(() => {
    const shortcut = readShortcut(params)
    if (!shortcut || handled.current === location.key) return
    handled.current = location.key
    setParams(withoutShortcut(params), { replace: true })
    if (shortcut.add) setSheet({ open: true, date: todayISO(), text: shortcut.text })
    if (shortcut.waterMl) {
      const today = todayISO()
      const ml = shortcut.waterMl
      const entry = addWater(today, ml)
      haptic('success')
      toast({ title: `+${fmtWater(ml)} de agua`, action: { label: 'Deshacer', onClick: () => removeWater(today, entry.client_id) } })
    }
  }, [params, setParams, location.key, addWater, removeWater])

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
            <Suspense fallback={<PageFallback />}>{children(location)}</Suspense>
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
        {/* Se carga en un momento ocioso: al pulsar "+" ya suele estar lista, y si no, se monta al pulsar. */}
        {(sheetReady || sheet.open) && (
          <AddMealSheet
            open={sheet.open}
            date={sheet.date}
            slot={sheet.slot}
            text={sheet.text}
            onClose={() => setSheet((s) => ({ ...s, open: false }))}
            onNewProduct={() => {
              setSheet((s) => ({ ...s, open: false }))
              openProduct(null)
            }}
            onSaved={(date) => {
              if (location.pathname !== '/' || date !== viewedDate) navigate(date === todayISO() ? '/' : `/?fecha=${date}`)
            }}
          />
        )}
      </Suspense>
      <Suspense fallback={null}>
        {(productEver || productSheet.open) && (
          <ProductSheet open={productSheet.open} product={productSheet.product} onClose={() => setProductSheet((p) => ({ ...p, open: false }))} />
        )}
      </Suspense>
      <Confetti run={confetti} />
    </Context.Provider>
  )
}

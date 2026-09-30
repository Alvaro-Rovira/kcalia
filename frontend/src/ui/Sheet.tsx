import { AnimatePresence, motion, useDragControls, useReducedMotion } from 'motion/react'
import { X } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  open: boolean
  onClose: () => void
  title: string
  /** Oculta visualmente el título (sigue existiendo para lectores de pantalla). */
  hideTitle?: boolean
  children: ReactNode
  footer?: ReactNode
  /** El contenido ocupa casi toda la pantalla. */
  tall?: boolean
}

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select, [tabindex]:not([tabindex="-1"])'

/** Espacio que ocupa el teclado en pantalla, para que la hoja no quede debajo (iOS). */
function useKeyboardInset(active: boolean, target: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const viewport = window.visualViewport
    if (!active || !viewport) return
    const update = () => {
      const inset = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop)
      target.current?.style.setProperty('--kb', `${inset}px`)
    }
    update()
    viewport.addEventListener('resize', update)
    viewport.addEventListener('scroll', update)
    return () => {
      viewport.removeEventListener('resize', update)
      viewport.removeEventListener('scroll', update)
    }
  }, [active, target])
}

/** Hoja modal inferior: se arrastra para cerrar, atrapa el foco y cierra con Escape. */
export function Sheet({ open, onClose, title, hideTitle, children, footer, tall }: Props) {
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)
  const controls = useDragControls()
  const reduce = useReducedMotion()
  useKeyboardInset(open, panel)
  // onClose suele ser una función nueva en cada render del padre. Si el efecto dependiera de
  // ella, cada tecla pulsada dentro de la hoja le quitaría el foco al campo.
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab' || !panel.current) return
      const nodes = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((n) => n.offsetParent !== null)
      if (!nodes.length) return
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    // El foco entra en la hoja si el contenido no lo ha pedido ya (autoFocus).
    const timer = setTimeout(() => {
      if (panel.current && !panel.current.contains(document.activeElement)) panel.current.focus()
    }, 60)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      previous?.focus?.()
    }
  }, [open])

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center lg:items-center lg:p-8">
          <motion.div
            className="absolute inset-0 bg-scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22 }}
            onClick={onClose}
            aria-hidden
          />
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            drag={reduce ? false : 'y'}
            dragControls={controls}
            dragListener={false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.55 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 110 || info.velocity.y > 700) onClose()
            }}
            initial={reduce ? { opacity: 0 } : { y: '100%' }}
            animate={reduce ? { opacity: 1 } : { y: 0 }}
            exit={reduce ? { opacity: 0 } : { y: '100%' }}
            transition={{ type: 'spring', stiffness: 380, damping: 38, mass: 0.9 }}
            className={`glass relative flex w-full max-w-[560px] flex-col rounded-t-xl shadow-lg outline-none lg:rounded-xl ${
              tall ? 'h-[92dvh] lg:h-auto lg:max-h-[86dvh]' : 'max-h-[92dvh] lg:max-h-[86dvh]'
            }`}
            style={{ paddingBottom: 'var(--kb, 0px)' }}
          >
            <div
              className="flex shrink-0 touch-none flex-col items-center pt-2.5 lg:hidden"
              onPointerDown={(event) => controls.start(event)}
            >
              <div className="h-1.5 w-10 rounded-full bg-border-strong" aria-hidden />
            </div>
            <div
              className={`flex shrink-0 items-center justify-between gap-3 pr-2.5 pl-5 ${hideTitle ? 'h-2 lg:h-12' : 'pt-2 pb-1 lg:pt-4'}`}
              onPointerDown={(event) => {
                if (!(event.target as HTMLElement).closest('button')) controls.start(event)
              }}
            >
              <h2 id={titleId} className={hideTitle ? 'sr-only' : 'text-[19px] font-semibold tracking-[-0.02em] text-text'}>
                {title}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Cerrar"
                className={`grid size-11 place-items-center rounded-full text-text-3 transition-colors hover:bg-surface-2 hover:text-text ${
                  hideTitle ? 'absolute top-2 right-2.5 z-10 hidden lg:grid' : ''
                }`}
              >
                <X className="size-5" aria-hidden />
              </button>
            </div>
            <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pt-1 pb-5">{children}</div>
            {footer && (
              <div
                className="shrink-0 border-t border-border px-5 pt-3"
                style={{ paddingBottom: 'calc(max(var(--safe-b), 14px))' }}
              >
                {footer}
              </div>
            )}
            {!footer && <div style={{ height: 'var(--safe-b)' }} aria-hidden />}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  )
}

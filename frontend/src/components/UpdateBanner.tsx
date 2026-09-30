import { AnimatePresence, motion } from 'motion/react'
import { RefreshCw } from 'lucide-react'
import { useRegisterSW } from 'virtual:pwa-register/react'

const HOUR = 60 * 60 * 1000

/** Aviso de "nueva versión disponible" cuando el service worker nuevo está listo. */
export function UpdateBanner() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      // Una PWA instalada puede pasar días abierta: se busca versión nueva cada hora.
      if (registration) setInterval(() => void registration.update().catch(() => undefined), HOUR)
    },
  })

  return (
    <AnimatePresence>
      {needRefresh && (
        <motion.div
          role="status"
          initial={{ opacity: 0, y: -24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -24 }}
          transition={{ type: 'spring', stiffness: 420, damping: 34 }}
          className="fixed inset-x-0 top-0 z-[80] flex justify-center px-4"
          style={{ paddingTop: 'calc(var(--safe-t) + 10px)' }}
        >
          <div className="glass flex w-full max-w-[420px] items-center gap-3 rounded-lg py-2 pr-2 pl-4 shadow-lg">
            <RefreshCw className="size-[18px] shrink-0 text-accent-text" aria-hidden />
            <p className="min-w-0 flex-1 text-[14.5px] font-medium text-text">Nueva versión disponible</p>
            <button
              type="button"
              onClick={() => void updateServiceWorker(true)}
              className="h-11 shrink-0 rounded-sm bg-accent px-4 text-[14px] font-semibold text-on-accent active:opacity-80"
            >
              Actualizar
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

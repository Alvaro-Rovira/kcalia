import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { MotionConfig } from 'motion/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import App, { preloadRoute } from './App'
import { outbox, type Op } from './offline/outbox'
import { CACHE_BUSTER, CACHE_MAX_AGE, keys, persister, queryClient } from './offline/queryClient'
import './styles/index.css'
import { toast } from './ui/toast'

const REJECTED: Record<Op['type'], string> = {
  'meal.create': 'No se ha podido guardar una comida',
  'meal.patch': 'No se ha podido guardar un cambio',
  'meal.delete': 'No se ha podido borrar una comida',
  'meal.restore': 'No se ha podido recuperar una comida',
  'weight.put': 'No se ha podido guardar un peso',
  'weight.delete': 'No se ha podido borrar un peso',
  'dish.patch': 'No se ha podido actualizar un favorito',
}

preloadRoute(location.pathname)

outbox.init({
  // Lo que acaba de llegar al servidor puede cambiar totales, racha, resúmenes e historial.
  onSynced: (types) => {
    const touchesMeals = [...types].some((t) => t.startsWith('meal.'))
    if (touchesMeals) {
      for (const key of ['meals', 'days', 'week'] as const) void queryClient.invalidateQueries({ queryKey: [key] })
      void queryClient.invalidateQueries({ queryKey: keys.summaries })
    }
    if ([...types].some((t) => t.startsWith('weight.'))) {
      void queryClient.invalidateQueries({ queryKey: keys.weight })
      void queryClient.invalidateQueries({ queryKey: ['week'] })
    }
    void queryClient.invalidateQueries({ queryKey: keys.stats })
    void queryClient.invalidateQueries({ queryKey: keys.bootstrap })
  },
  onRejected: (op, error) => toast.error(REJECTED[op.type], error.message),
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{ persister, maxAge: CACHE_MAX_AGE, buster: CACHE_BUSTER }}
    >
      {/* "user": las animaciones de movimiento se reducen solas con prefers-reduced-motion. */}
      <MotionConfig reducedMotion="user">
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </MotionConfig>
    </PersistQueryClientProvider>
  </StrictMode>,
)

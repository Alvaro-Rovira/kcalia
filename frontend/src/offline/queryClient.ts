import { QueryClient } from '@tanstack/react-query'
import type { PersistedClient, Persister } from '@tanstack/react-query-persist-client'
import { del, get, set } from 'idb-keyval'
import { ApiError } from '@/lib/api'

const WEEK = 7 * 24 * 60 * 60 * 1000
const CACHE_KEY = 'kcalia:cache'

export const CACHE_MAX_AGE = WEEK
/** Cambiar este valor descarta la caché guardada de versiones anteriores. */
export const CACHE_BUSTER = 'v1'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Con datos en caché se pinta primero y se revalida después: así funciona sin red.
      networkMode: 'offlineFirst',
      staleTime: 30_000,
      gcTime: WEEK,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      retry: (failures, error) => {
        if (error instanceof ApiError && (error.offline || error.status < 500)) return false
        return failures < 2
      },
    },
    mutations: { networkMode: 'always', retry: false },
  },
})

let timer: ReturnType<typeof setTimeout> | undefined
let latest: PersistedClient | undefined

function writeNow(): void {
  if (timer) clearTimeout(timer)
  timer = undefined
  if (latest) void set(CACHE_KEY, latest).catch(() => undefined)
}

if (typeof document !== 'undefined') {
  // Una PWA puede cerrarse en cualquier momento: al ocultarse se guarda sin esperar al retardo.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') writeNow()
  })
  window.addEventListener('pagehide', writeNow)
}

/** Caché de React Query persistida en IndexedDB (el diario se ve sin conexión). */
export const persister: Persister = {
  persistClient: (client) => {
    latest = client
    if (timer) return
    timer = setTimeout(writeNow, 800)
  },
  restoreClient: () => get<PersistedClient>(CACHE_KEY).catch(() => undefined),
  removeClient: () => del(CACHE_KEY).catch(() => undefined),
}

export async function clearLocalData(): Promise<void> {
  if (timer) clearTimeout(timer)
  timer = undefined
  latest = undefined
  queryClient.clear()
  await del(CACHE_KEY).catch(() => undefined)
}

export const keys = {
  auth: ['auth'] as const,
  bootstrap: ['bootstrap'] as const,
  meals: (date: string) => ['meals', date] as const,
  days: (start: string, end: string) => ['days', start, end] as const,
  weight: ['weight'] as const,
  week: (start: string) => ['week', start] as const,
  summaries: ['summaries'] as const,
  stats: ['stats'] as const,
  water: (date: string) => ['water', date] as const,
  waterDays: (start: string, end: string) => ['water', 'days', start, end] as const,
  measurements: ['measurements'] as const,
  training: ['training'] as const,
  exerciseHistory: (cid: string) => ['training', 'history', cid] as const,
  photos: ['photos'] as const,
}

import { useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Route, Routes } from 'react-router'
import { Shell } from './components/Shell'
import { Splash } from './components/Splash'
import { UpdateBanner } from './components/UpdateBanner'
import { useAuthStatus, useBootstrap } from './hooks/data'
import { UNAUTHORIZED_EVENT } from './lib/api'
import type { AuthStatus } from './lib/types'
import { keys } from './offline/queryClient'
import Auth from './pages/Auth'
import Today from './pages/Today'
import { Button } from './ui/Button'
import { EmptyState } from './ui/EmptyState'
import { Toaster } from './ui/toast'

const loaders = {
  '/historial': () => import('./pages/History'),
  '/resumen': () => import('./pages/Summary'),
  '/peso': () => import('./pages/Weight'),
  '/ajustes': () => import('./pages/Settings'),
}

/** Empieza a descargar la pantalla de la URL actual en paralelo con la sesión y los datos. */
export function preloadRoute(pathname: string): void {
  const loader = loaders[pathname as keyof typeof loaders]
  if (loader) void loader()
}

const Onboarding = lazy(() => import('./pages/Onboarding'))
const History = lazy(loaders['/historial'])
const Summary = lazy(loaders['/resumen'])
const WeightPage = lazy(loaders['/peso'])
const Settings = lazy(loaders['/ajustes'])
const NotFound = lazy(() => import('./pages/NotFound'))

function CannotConnect({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="grid min-h-dvh place-items-center px-6">
      <EmptyState
        art="offline"
        title="No hay conexión"
        text="No he podido llegar al servidor y aún no hay nada guardado en este dispositivo."
        action={<Button onClick={onRetry}>Reintentar</Button>}
      />
    </main>
  )
}

function AuthedApp() {
  const bootstrap = useBootstrap()
  if (!bootstrap.data) {
    return bootstrap.isError ? <CannotConnect onRetry={() => void bootstrap.refetch()} /> : <Splash />
  }
  if (!bootstrap.data.profile || !bootstrap.data.targets) {
    return (
      <Suspense fallback={<Splash />}>
        <Onboarding />
      </Suspense>
    )
  }
  return (
    <Shell>
      {(location) => (
        <Routes location={location}>
          <Route path="/" element={<Today />} />
          <Route path="/historial" element={<History />} />
          <Route path="/resumen" element={<Summary />} />
          <Route path="/peso" element={<WeightPage />} />
          <Route path="/ajustes" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      )}
    </Shell>
  )
}

export default function App() {
  const client = useQueryClient()
  const auth = useAuthStatus()
  const [expired, setExpired] = useState(false)

  useEffect(() => {
    // Un 401 en mitad del uso: la sesión ha caducado. Se pide entrar de nuevo sin perder nada.
    const onUnauthorized = () => {
      const current = client.getQueryData<AuthStatus>(keys.auth)
      if (current?.authenticated) setExpired(true)
      client.setQueryData<AuthStatus>(keys.auth, (old) => (old ? { ...old, authenticated: false } : old))
    }
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [client])

  useEffect(() => {
    if (auth.data?.authenticated) setExpired(false)
  }, [auth.data?.authenticated])

  let screen
  if (!auth.data) {
    screen = auth.isError ? <CannotConnect onRetry={() => void auth.refetch()} /> : <Splash />
  } else if (!auth.data.authenticated && auth.isFetching && !expired) {
    // Lo guardado dice "sin sesión": se confirma antes de enseñar el login.
    screen = <Splash />
  } else if (!auth.data.authenticated) {
    screen = <Auth registered={auth.data.registered} expired={expired} />
  } else {
    screen = <AuthedApp />
  }

  return (
    <>
      {screen}
      <Toaster />
      <UpdateBanner />
    </>
  )
}

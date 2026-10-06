import { useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Route, Routes } from 'react-router'
import { Shell } from './components/Shell'
import { Splash } from './components/Splash'
import { UpdateBanner } from './components/UpdateBanner'
import { useAuthStatus, useBootstrap } from './hooks/data'
import { ACCOUNT_EVENT, UNAUTHORIZED_EVENT } from './lib/api'
import type { AuthStatus } from './lib/types'
import { keys } from './offline/queryClient'
import AccountStatus from './pages/AccountStatus'
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
  '/admin': () => import('./pages/Admin'),
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
const Admin = lazy(loaders['/admin'])
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
          {/* Solo existe para el administrador; para el resto es una ruta desconocida (y la API responde 403). */}
          {bootstrap.data.user.is_admin && <Route path="/admin" element={<Admin />} />}
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
    // La cuenta ha pasado a pendiente o bloqueada: se vuelve a preguntar por la sesión y se enseña su estado.
    const onAccount = () => void client.invalidateQueries({ queryKey: keys.auth })
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    window.addEventListener(ACCOUNT_EVENT, onAccount)
    return () => {
      window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
      window.removeEventListener(ACCOUNT_EVENT, onAccount)
    }
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
    screen = <Auth registered={auth.data.registered} signup={auth.data.signup} expired={expired} />
  } else if (auth.data.status === 'pending' || auth.data.status === 'suspended') {
    screen = <AccountStatus status={auth.data.status} username={auth.data.username} />
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

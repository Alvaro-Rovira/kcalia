import { useQueryClient } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { Hourglass, LogOut, RefreshCw, ShieldOff } from 'lucide-react'
import { useState } from 'react'
import { Logo, Wordmark } from '@/components/Logo'
import { api } from '@/lib/api'
import type { AccountStatus as Status } from '@/lib/types'
import { clearOutbox } from '@/offline/outbox'
import { clearLocalData, keys } from '@/offline/queryClient'
import { Button } from '@/ui/Button'

const COPY: Record<Exclude<Status, 'approved'>, { title: string; text: string; Icon: typeof Hourglass; tone: string }> = {
  pending: {
    title: 'Tu cuenta está pendiente de aprobación',
    text: 'El administrador tiene que aprobarla antes de que puedas usar Kcalia. Mientras tanto no se guarda nada ni se usa la IA. Vuelve en otro momento o comprueba ahora si ya está lista.',
    Icon: Hourglass,
    tone: 'bg-warn-soft text-warn-text',
  },
  suspended: {
    title: 'Tu cuenta está bloqueada',
    text: 'El administrador ha bloqueado esta cuenta y no se puede usar. Tus datos no se han borrado. Si crees que es un error, habla con quien administra esta instalación.',
    Icon: ShieldOff,
    tone: 'bg-danger-soft text-danger-text',
  },
}

/** Lo único que ve una cuenta sin aprobar o bloqueada: su estado y la opción de salir. */
export default function AccountStatus({ status, username }: { status: Exclude<Status, 'approved'>; username: string | null }) {
  const client = useQueryClient()
  const [checking, setChecking] = useState(false)
  const { title, text, Icon, tone } = COPY[status]

  async function check() {
    setChecking(true)
    try {
      await client.refetchQueries({ queryKey: keys.auth })
    } finally {
      setChecking(false)
    }
  }

  async function logout() {
    try {
      await api.post('/api/auth/logout')
    } catch {
      // Sin red también se sale: se borra lo guardado en este dispositivo.
    }
    await clearOutbox()
    await clearLocalData()
    window.location.assign('/')
  }

  return (
    <main
      className="mx-auto flex min-h-dvh w-full max-w-[420px] flex-col justify-center px-6 py-10"
      style={{ paddingTop: 'calc(var(--safe-t) + 40px)', paddingBottom: 'calc(var(--safe-b) + 32px)' }}
    >
      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}>
        <div className="flex items-center gap-3">
          <Logo size={44} />
          <Wordmark className="text-[28px]" />
        </div>
        <span className={`mt-10 grid size-14 place-items-center rounded-full ${tone}`}>
          <Icon className="size-7" aria-hidden />
        </span>
        <h1 className="mt-5 text-[27px] leading-tight font-semibold tracking-[-0.03em] text-text">{title}</h1>
        <p className="mt-3 text-[15.5px] leading-relaxed text-text-2">{text}</p>
        {username && <p className="mt-4 text-[14px] text-text-3">Sesión iniciada como {username}</p>}
        <div className="mt-8 space-y-2.5">
          {status === 'pending' && (
            <Button size="lg" block loading={checking} onClick={() => void check()} icon={<RefreshCw className="size-[18px]" aria-hidden />}>
              Comprobar de nuevo
            </Button>
          )}
          <Button size="lg" block variant="secondary" onClick={() => void logout()} icon={<LogOut className="size-[18px]" aria-hidden />}>
            Cerrar sesión
          </Button>
        </div>
      </motion.div>
    </main>
  )
}

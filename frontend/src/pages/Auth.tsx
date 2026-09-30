import { useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { Eye, EyeOff, LockKeyhole, UserPlus } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Logo, Wordmark } from '@/components/Logo'
import { api, ApiError, errorMessage } from '@/lib/api'
import { haptic } from '@/lib/haptics'
import { keys } from '@/offline/queryClient'
import { Button } from '@/ui/Button'
import { Field } from '@/ui/Field'
import { Notice } from '@/ui/Notice'

interface Props {
  /** Ya existe la cuenta de esta instalación: el registro está cerrado. */
  registered: boolean
  /** La sesión ha caducado mientras se usaba la app. */
  expired?: boolean
}

type Mode = 'login' | 'register'

const COPY: Record<Mode, { title: string; text: string; submit: string }> = {
  login: { title: 'Inicia sesión', text: 'Entra para seguir con tu diario.', submit: 'Entrar' },
  register: {
    title: 'Crea tu cuenta',
    text: 'Esta instalación es solo para ti: en cuanto crees la cuenta, el registro se cierra.',
    submit: 'Crear cuenta',
  },
}

/** Inicio de sesión, con la opción de crear la cuenta mientras todavía no exista ninguna. */
export default function Auth({ registered, expired }: Props) {
  const client = useQueryClient()
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const register = mode === 'register' && !registered
  const copy = COPY[register ? 'register' : 'login']
  const tooShort = register && password.length > 0 && password.length < 8

  // Si la cuenta se crea desde otro dispositivo mientras tanto, aquí ya solo cabe entrar.
  useEffect(() => {
    if (registered) setMode('login')
  }, [registered])

  function switchTo(next: Mode) {
    haptic('select')
    setMode(next)
    setError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    if (username.trim().length < 2) return setError('Escribe un nombre de usuario de al menos 2 letras.')
    if (password.length < 8) return setError('La contraseña debe tener al menos 8 caracteres.')
    if (!register && !registered) {
      // Sin cuenta creada no hay con qué comparar: mejor decirlo que dar un "contraseña incorrecta".
      haptic('warning')
      return setError('Todavía no existe ninguna cuenta en esta instalación. Créala primero con el enlace de abajo.')
    }
    setBusy(true)
    setError('')
    try {
      await api.post(`/api/auth/${register ? 'register' : 'login'}`, { username: username.trim(), password })
      haptic('success')
      await client.invalidateQueries({ queryKey: keys.bootstrap })
      await client.invalidateQueries({ queryKey: keys.auth })
    } catch (err) {
      setError(errorMessage(err))
      haptic('error')
      // 403 al registrar: alguien creó la cuenta entre tanto. Se refresca el estado y se pasa a "Entrar".
      if (register && err instanceof ApiError && err.status === 403) void client.invalidateQueries({ queryKey: keys.auth })
    } finally {
      setBusy(false)
    }
  }

  return (
    <main
      className="mx-auto flex min-h-dvh w-full max-w-[420px] flex-col justify-center px-6 py-10"
      style={{ paddingTop: 'calc(var(--safe-t) + 40px)', paddingBottom: 'calc(var(--safe-b) + 32px)' }}
    >
      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}>
        <div className="flex items-center gap-3">
          <Logo size={52} />
          <Wordmark className="text-[34px]" />
        </div>

        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={expired ? 'expired' : register ? 'register' : 'login'}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6, transition: { duration: 0.12 } }}
            transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
          >
            <h1 className="mt-8 text-[28px] leading-tight font-semibold tracking-[-0.03em] text-text">
              {expired ? 'Tu sesión ha caducado' : registered && !register ? 'Hola de nuevo' : copy.title}
            </h1>
            <p className="mt-2 text-[15.5px] leading-relaxed text-text-2">
              {expired ? 'Por seguridad hay que volver a entrar. Tus datos siguen donde los dejaste.' : copy.text}
            </p>
          </motion.div>
        </AnimatePresence>

        <form onSubmit={submit} className="mt-8 space-y-4" noValidate>
          <Field
            label="Usuario"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="next"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
          <Field
            label="Contraseña"
            name="password"
            type={visible ? 'text' : 'password'}
            autoComplete={register ? 'new-password' : 'current-password'}
            enterKeyHint="go"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            hint={register ? 'Mínimo 8 caracteres. Se guarda cifrada (Argon2).' : undefined}
            error={tooShort ? `Faltan ${8 - password.length} caracteres.` : undefined}
            suffix={
              <button
                type="button"
                onClick={() => setVisible((v) => !v)}
                aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                aria-pressed={visible}
                className="-mr-2 grid size-11 place-items-center text-text-3"
              >
                {visible ? <EyeOff className="size-5" aria-hidden /> : <Eye className="size-5" aria-hidden />}
              </button>
            }
          />
          {error && <Notice level="danger">{error}</Notice>}
          <Button
            type="submit"
            size="lg"
            block
            loading={busy}
            icon={register ? <UserPlus className="size-[18px]" aria-hidden /> : <LockKeyhole className="size-[18px]" aria-hidden />}
          >
            {copy.submit}
          </Button>
        </form>

        {/* La opción de crear cuenta solo existe mientras no haya ninguna: después el registro queda cerrado. */}
        {!registered && (
          <p className="mt-5 text-center text-[14.5px] text-text-2">
            {register ? '¿Ya tienes cuenta?' : '¿Aún no tienes cuenta?'}{' '}
            <button
              type="button"
              onClick={() => switchTo(register ? 'login' : 'register')}
              className="inline-flex min-h-11 items-center px-1 font-semibold text-accent-text underline-offset-4 hover:underline"
            >
              {register ? 'Inicia sesión' : 'Créala ahora'}
            </button>
          </p>
        )}
      </motion.div>
    </main>
  )
}

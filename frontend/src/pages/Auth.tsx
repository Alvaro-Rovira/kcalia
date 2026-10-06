import { useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { Eye, EyeOff, LockKeyhole, MailCheck, Send, UserPlus } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Logo, Wordmark } from '@/components/Logo'
import { api, ApiError, errorMessage } from '@/lib/api'
import { haptic } from '@/lib/haptics'
import type { SignupState } from '@/lib/types'
import { keys } from '@/offline/queryClient'
import { Button } from '@/ui/Button'
import { Field } from '@/ui/Field'
import { Notice } from '@/ui/Notice'

interface Props {
  /** Ya existe alguna cuenta en esta instalación. */
  registered: boolean
  /** first, open, closed o full (ver backend: auth.signup_state). */
  signup?: SignupState
  /** La sesión ha caducado mientras se usaba la app. */
  expired?: boolean
}

type Mode = 'login' | 'create' | 'request' | 'sent'

const MIN_PASSWORD = 10
const USERNAME = /^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$/

const COPY: Record<Exclude<Mode, 'sent'>, { title: string; text: string; submit: string }> = {
  login: { title: 'Inicia sesión', text: 'Entra para seguir con tu diario.', submit: 'Entrar' },
  create: {
    title: 'Crea tu cuenta',
    text: 'Es la primera cuenta de esta instalación: serás quien administre y apruebe las cuentas nuevas.',
    submit: 'Crear cuenta',
  },
  request: {
    title: 'Solicita una cuenta',
    text: 'Cuando el administrador la apruebe podrás entrar con este usuario y contraseña.',
    submit: 'Enviar solicitud',
  },
}

/** Inicio de sesión, con la opción de crear la primera cuenta o de solicitar una. */
export default function Auth({ registered, signup, expired }: Props) {
  const client = useQueryClient()
  const state: SignupState = signup ?? (registered ? 'closed' : 'first')
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [website, setWebsite] = useState('')
  const [visible, setVisible] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const creating = mode === 'create' || mode === 'request'
  const tooShort = creating && password.length > 0 && password.length < MIN_PASSWORD

  // Si la primera cuenta se crea desde otro dispositivo mientras tanto, aquí ya solo cabe solicitar o entrar.
  useEffect(() => {
    if (state !== 'first' && mode === 'create') setMode('login')
  }, [state, mode])

  function switchTo(next: Mode) {
    haptic('select')
    setMode(next)
    setError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    const name = username.trim()
    if (creating && !USERNAME.test(name)) {
      return setError('El usuario debe tener de 3 a 32 caracteres: letras sin tildes, números, punto, guion o guion bajo.')
    }
    if (!creating && !name) return setError('Escribe tu usuario.')
    if (creating && password.length < MIN_PASSWORD) return setError(`La contraseña debe tener al menos ${MIN_PASSWORD} caracteres.`)
    if (!creating && !password) return setError('Escribe tu contraseña.')
    if (mode === 'login' && state === 'first') {
      // Sin cuenta creada no hay con qué comparar: mejor decirlo que dar un "contraseña incorrecta".
      haptic('warning')
      return setError('Todavía no existe ninguna cuenta en esta instalación. Créala primero con el enlace de abajo.')
    }
    setBusy(true)
    setError('')
    try {
      if (mode === 'login') {
        await api.post('/api/auth/login', { username: name, password })
      } else {
        await api.post('/api/auth/register', { username: name, password, website })
      }
      haptic('success')
      if (mode === 'request') {
        // Sin refrescar la sesión: mientras se comprueba, la app enseña la pantalla de carga y esto se perdería.
        setPassword('')
        setMode('sent')
        return
      }
      await client.invalidateQueries({ queryKey: keys.bootstrap })
      await client.invalidateQueries({ queryKey: keys.auth })
    } catch (err) {
      setError(errorMessage(err))
      haptic('error')
      // El estado del registro ha cambiado entre tanto (cerrado, lleno o ya hay cuenta): se refresca.
      if (creating && err instanceof ApiError && (err.status === 403 || err.status === 503)) {
        void client.invalidateQueries({ queryKey: keys.auth })
      }
    } finally {
      setBusy(false)
    }
  }

  const copy = mode === 'sent' ? null : COPY[mode]
  const heading = expired ? 'Tu sesión ha caducado' : mode === 'login' && registered ? 'Hola de nuevo' : copy?.title
  const intro = expired ? 'Por seguridad hay que volver a entrar. Tus datos siguen donde los dejaste.' : copy?.text

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
          {mode === 'sent' ? (
            <motion.div key="sent" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-8">
              <span className="grid size-14 place-items-center rounded-full bg-accent-soft text-accent-text">
                <MailCheck className="size-7" aria-hidden />
              </span>
              <h1 className="mt-5 text-[28px] leading-tight font-semibold tracking-[-0.03em] text-text">Solicitud enviada</h1>
              <p className="mt-2 text-[15.5px] leading-relaxed text-text-2" role="status">
                Cuando el administrador la apruebe podrás entrar con tu usuario y contraseña. Si el nombre de usuario ya estaba
                cogido, no podrás entrar: prueba a solicitarla con otro.
              </p>
              <Button size="lg" block className="mt-8" onClick={() => switchTo('login')} icon={<LockKeyhole className="size-[18px]" aria-hidden />}>
                Ir a iniciar sesión
              </Button>
            </motion.div>
          ) : (
            <motion.div
              key={expired ? 'expired' : mode}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6, transition: { duration: 0.12 } }}
              transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
            >
              <h1 className="mt-8 text-[28px] leading-tight font-semibold tracking-[-0.03em] text-text">{heading}</h1>
              <p className="mt-2 text-[15.5px] leading-relaxed text-text-2">{intro}</p>
            </motion.div>
          )}
        </AnimatePresence>

        {mode !== 'sent' && copy && (
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
              hint={creating ? 'De 3 a 32 caracteres: letras sin tildes, números, punto o guion.' : undefined}
              autoFocus
            />
            <Field
              label="Contraseña"
              name="password"
              type={visible ? 'text' : 'password'}
              autoComplete={creating ? 'new-password' : 'current-password'}
              enterKeyHint="go"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              hint={creating ? `Mínimo ${MIN_PASSWORD} caracteres. Se guarda cifrada (Argon2).` : undefined}
              error={tooShort ? `Faltan ${MIN_PASSWORD - password.length} caracteres.` : undefined}
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
            {mode === 'request' && (
              // Campo trampa: fuera de la vista y del orden de tabulación. Una persona no lo rellena; un robot, sí.
              <div aria-hidden className="absolute -left-[9999px] h-px w-px overflow-hidden">
                <label>
                  Web
                  <input name="website" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
                </label>
              </div>
            )}
            {error && <Notice level="danger">{error}</Notice>}
            <Button
              type="submit"
              size="lg"
              block
              loading={busy}
              icon={
                mode === 'create' ? (
                  <UserPlus className="size-[18px]" aria-hidden />
                ) : mode === 'request' ? (
                  <Send className="size-[18px]" aria-hidden />
                ) : (
                  <LockKeyhole className="size-[18px]" aria-hidden />
                )
              }
            >
              {copy.submit}
            </Button>
          </form>
        )}

        {mode !== 'sent' && <SwitchLink mode={mode} state={state} onSwitch={switchTo} />}
      </motion.div>
    </main>
  )
}

function SwitchLink({ mode, state, onSwitch }: { mode: Mode; state: SignupState; onSwitch: (mode: Mode) => void }) {
  const link = (label: string, next: Mode) => (
    <button
      type="button"
      onClick={() => onSwitch(next)}
      className="inline-flex min-h-11 items-center px-1 font-semibold text-accent-text underline-offset-4 hover:underline"
    >
      {label}
    </button>
  )
  if (mode !== 'login') {
    return <p className="mt-5 text-center text-[14.5px] text-text-2">¿Ya tienes cuenta? {link('Inicia sesión', 'login')}</p>
  }
  if (state === 'first') {
    return <p className="mt-5 text-center text-[14.5px] text-text-2">¿Aún no tienes cuenta? {link('Créala ahora', 'create')}</p>
  }
  if (state === 'open') {
    return <p className="mt-5 text-center text-[14.5px] text-text-2">¿No tienes cuenta? {link('Solicítala', 'request')}</p>
  }
  if (state === 'full') {
    return (
      <p className="mt-5 text-center text-[14px] leading-relaxed text-text-3">
        Las solicitudes de cuenta están en pausa: hay muchas pendientes de revisar.
      </p>
    )
  }
  return null
}

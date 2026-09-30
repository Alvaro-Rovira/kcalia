import { useQueryClient } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { Eye, EyeOff, LockKeyhole } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Logo, Wordmark } from '@/components/Logo'
import { api, errorMessage } from '@/lib/api'
import { haptic } from '@/lib/haptics'
import { keys } from '@/offline/queryClient'
import { Button } from '@/ui/Button'
import { Field } from '@/ui/Field'
import { Notice } from '@/ui/Notice'

interface Props {
  mode: 'login' | 'register'
  /** La sesión ha caducado mientras se usaba la app. */
  expired?: boolean
}

export default function Auth({ mode, expired }: Props) {
  const client = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const register = mode === 'register'
  const tooShort = register && password.length > 0 && password.length < 8

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    if (username.trim().length < 2) return setError('Escribe un nombre de usuario de al menos 2 letras.')
    if (password.length < 8) return setError('La contraseña debe tener al menos 8 caracteres.')
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
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-[420px] flex-col justify-center px-6 py-10" style={{ paddingTop: 'calc(var(--safe-t) + 40px)' }}>
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="flex items-center gap-3">
          <Logo size={52} />
          <Wordmark className="text-[34px]" />
        </div>
        <h1 className="mt-8 text-[28px] leading-tight font-semibold tracking-[-0.03em] text-text">
          {expired ? 'Tu sesión ha caducado' : register ? 'Crea tu cuenta' : 'Hola de nuevo'}
        </h1>
        <p className="mt-2 text-[15.5px] leading-relaxed text-text-2">
          {expired
            ? 'Por seguridad hay que volver a entrar. Tus datos siguen donde los dejaste.'
            : register
              ? 'Calorías y macros con calma. Esta instalación es solo para ti: al crear la cuenta, el registro se cierra.'
              : 'Entra para seguir con tu diario.'}
        </p>

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
          <Button type="submit" size="lg" block loading={busy} icon={<LockKeyhole className="size-[18px]" aria-hidden />}>
            {register ? 'Crear cuenta' : 'Entrar'}
          </Button>
        </form>
      </motion.div>
    </main>
  )
}

import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { motion } from 'motion/react'
import { Ban, Check, CircleCheck, Hourglass, KeyRound, LogOut, Mic, ShieldOff, Sparkles, Trash2, UserCheck, X } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { adminKeys, useAdminAudit, useAdminOverview, useAdminUsers, type AdminUser, type AuditEntry, type BackupStatus } from '@/hooks/admin'
import { useOnline } from '@/hooks/data'
import { api, errorMessage } from '@/lib/api'
import { fmtAgo } from '@/lib/dates'
import { fmt, plural } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { Button } from '@/ui/Button'
import { EmptyState } from '@/ui/EmptyState'
import { Field, NumberInput } from '@/ui/Field'
import { Notice } from '@/ui/Notice'
import { Sheet } from '@/ui/Sheet'
import { Skeleton } from '@/ui/Skeleton'
import { Switch } from '@/ui/Switch'
import { toast } from '@/ui/toast'

const STATUS: Record<AdminUser['status'], { label: string; Icon: typeof Hourglass; tone: string }> = {
  pending: { label: 'Pendiente', Icon: Hourglass, tone: 'bg-warn-soft text-warn-text' },
  approved: { label: 'Aprobada', Icon: CircleCheck, tone: 'bg-accent-soft text-accent-text' },
  suspended: { label: 'Bloqueada', Icon: ShieldOff, tone: 'bg-danger-soft text-danger-text' },
}

const ACTIONS: Record<string, string> = {
  approve: 'aprobó a',
  reject: 'rechazó la solicitud de',
  suspend: 'bloqueó a',
  unsuspend: 'desbloqueó a',
  delete: 'eliminó la cuenta de',
  limits: 'cambió los límites de',
  logout_all: 'cerró las sesiones de',
  settings: 'cambió los ajustes de la instalación',
  make_admin: 'pasó el rol de administrador a',
}

function money(value: number): string {
  if (value > 0 && value < 0.01) return '< 0,01 $'
  return `${fmt(value, 2)} $`
}

function StatusChip({ status }: { status: AdminUser['status'] }) {
  const { label, Icon, tone } = STATUS[status]
  return (
    <span className={clsx('inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-semibold', tone)}>
      <Icon className="size-3.5" aria-hidden />
      {label}
    </span>
  )
}

function Meter({ label, used, limit, Icon }: { label: string; used: number; limit: number; Icon: typeof Sparkles }) {
  const ratio = limit > 0 ? Math.min(1, used / limit) : 1
  const tone = ratio >= 1 ? 'bg-danger' : ratio >= 0.8 ? 'bg-warn' : 'bg-accent'
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-1.5 text-[14px] text-text-2">
          <Icon className="size-4 text-text-3" aria-hidden />
          {label}
        </span>
        <span className="text-[15px] font-semibold text-text" data-num>
          {fmt(used)} <span className="font-medium text-text-3">de {fmt(limit)}</span>
        </span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-track" role="meter" aria-valuemin={0} aria-valuemax={limit} aria-valuenow={used} aria-label={label}>
        <motion.div className={clsx('h-full rounded-full', tone)} initial={{ width: 0 }} animate={{ width: `${ratio * 100}%` }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }} />
      </div>
    </div>
  )
}

function Section({ title, id, children, aside }: { title: string; id: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="mt-7" aria-labelledby={id}>
      <div className="flex items-baseline justify-between gap-3 px-1">
        <h2 id={id} className="text-[17px] font-semibold tracking-[-0.01em] text-text">
          {title}
        </h2>
        {aside}
      </div>
      <div className="mt-2.5">{children}</div>
    </section>
  )
}

export default function Admin() {
  const client = useQueryClient()
  const online = useOnline()
  const overview = useAdminOverview(true)
  const users = useAdminUsers()
  const audit = useAdminAudit()
  const [selected, setSelected] = useState<AdminUser | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const refresh = () => Promise.all([adminKeys.overview, adminKeys.users, adminKeys.audit].map((queryKey) => client.invalidateQueries({ queryKey })))

  async function act(key: string, run: () => Promise<unknown>, success: string) {
    if (!online) {
      toast.error('Sin conexión', 'Las acciones de administración necesitan red.')
      return
    }
    setBusy(key)
    try {
      await run()
      haptic('success')
      toast.success(success)
      await refresh()
    } catch (error) {
      toast.error('No se ha podido hacer', errorMessage(error))
    } finally {
      setBusy(null)
    }
  }

  const pending = (users.data ?? []).filter((u) => u.status === 'pending')
  const accounts = (users.data ?? []).filter((u) => u.status !== 'pending')
  const data = overview.data

  return (
    <main className="page">
      <header>
        <h1 className="text-[30px] leading-tight font-semibold tracking-[-0.035em] text-text">Administración</h1>
        <p className="mt-1 text-[14.5px] text-text-2">Cuentas, gasto de IA y ajustes de esta instalación.</p>
      </header>

      <Section
        title="Solicitudes"
        id="adm-requests"
        aside={pending.length > 0 && <span className="text-[13.5px] font-medium text-warn-text" data-num>{pending.length} {plural(pending.length, 'pendiente', 'pendientes')}</span>}
      >
        {users.isPending ? (
          <Skeleton className="h-[92px] !rounded-[22px]" />
        ) : pending.length === 0 ? (
          <p className="card px-4 py-4 text-[14.5px] text-text-2">No hay solicitudes pendientes. Te avisaré aquí cuando alguien pida una cuenta.</p>
        ) : (
          <ul className="space-y-2.5">
            {pending.map((user) => (
              <li key={user.id} className="card p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-[16px] font-semibold text-text">{user.username}</p>
                    <p className="mt-0.5 text-[13px] text-text-3">Solicitada {fmtAgo(user.created_at)}</p>
                  </div>
                  <StatusChip status="pending" />
                </div>
                <div className="mt-3.5 grid grid-cols-2 gap-2.5">
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={busy === `reject-${user.id}`}
                    onClick={() => void act(`reject-${user.id}`, () => api.post(`/api/admin/users/${user.id}/reject`), `Solicitud de ${user.username} rechazada`)}
                    icon={<X className="size-4" aria-hidden />}
                  >
                    Rechazar
                  </Button>
                  <Button
                    size="sm"
                    loading={busy === `approve-${user.id}`}
                    onClick={() => void act(`approve-${user.id}`, () => api.post(`/api/admin/users/${user.id}/approve`), `${user.username} ya puede entrar`)}
                    icon={<Check className="size-4" aria-hidden />}
                  >
                    Aprobar
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <div className="lg:grid lg:grid-cols-2 lg:gap-x-6">
        <Section title="Gasto de hoy" id="adm-spend">
          <div className="card">
            {!data ? (
              <div className="p-4">
                <Skeleton className="h-24" />
              </div>
            ) : (
              <>
                <div className="space-y-4 border-b border-border p-4">
                  <Meter label="Consultas de IA, todas las cuentas" used={data.today.ai} limit={data.today.ai_limit} Icon={Sparkles} />
                  <Meter label="Audios transcritos" used={data.today.stt} limit={data.today.stt_limit} Icon={Mic} />
                </div>
                <dl className="grid grid-cols-2 divide-x divide-border border-b border-border text-center">
                  <div className="px-2 py-3">
                    <dt className="text-[12.5px] text-text-3">Coste estimado hoy</dt>
                    <dd className="mt-0.5 text-[18px] font-semibold text-text" data-num>{money(data.today.cost)}</dd>
                  </div>
                  <div className="px-2 py-3">
                    <dt className="text-[12.5px] text-text-3">Este mes</dt>
                    <dd className="mt-0.5 text-[18px] font-semibold text-text" data-num>{money(data.month.cost)}</dd>
                  </div>
                </dl>
                <p className="border-b border-border px-4 py-2.5 text-[13px] leading-relaxed text-text-3" data-num>
                  Hoy: {fmt(data.today.prompt_tokens)} tokens de entrada y {fmt(data.today.completion_tokens)} de salida. Precios por millón:{' '}
                  {fmt(data.prices.ai_input_per_million, 2)} $ y {fmt(data.prices.ai_output_per_million, 2)} $.
                </p>
                <Switch
                  label="Pausar la IA y la voz para todos"
                  description={data.ai_paused ? 'En pausa: nadie gasta crédito, tampoco tú. El historial y los productos siguen funcionando.' : 'Corta al momento cualquier consulta nueva a la IA.'}
                  checked={data.ai_paused}
                  disabled={busy === 'pause'}
                  onChange={(paused) =>
                    void act('pause', () => api.patch('/api/admin/settings', { ai_paused: paused }), paused ? 'IA en pausa para todos' : 'IA activada de nuevo')
                  }
                />
              </>
            )}
          </div>
        </Section>

        <Section title="Registro" id="adm-signup">
          <div className="card">
            {data && (
              <>
                <Switch
                  label="Admitir solicitudes de cuenta"
                  description={
                    !data.signup.allowed_by_server
                      ? 'Cerrado en el servidor (ALLOW_SIGNUP=false): este interruptor no tiene efecto.'
                      : data.signup.state === 'full'
                        ? `En pausa automática: hay ${data.signup.max_pending} solicitudes pendientes.`
                        : 'Toda cuenta nueva espera a que la apruebes.'
                  }
                  checked={data.signup.open}
                  disabled={busy === 'signup' || !data.signup.allowed_by_server}
                  onChange={(open) =>
                    void act('signup', () => api.patch('/api/admin/settings', { signup_open: open }), open ? 'Solicitudes abiertas' : 'Solicitudes cerradas')
                  }
                />
                <p className="border-t border-border px-4 py-2.5 text-[13px] leading-relaxed text-text-3" data-num>
                  Límites por defecto: {data.defaults.ai_user_daily_limit} consultas de IA y {data.defaults.stt_user_daily_limit} audios al día por
                  cuenta; el tuyo, {data.defaults.admin_ai_daily_limit}. El tope global no te bloquea a ti.
                </p>
              </>
            )}
          </div>
        </Section>
      </div>

      {data?.backup && (
        <Section title="Copias de seguridad" id="adm-backup">
          <BackupCard backup={data.backup} />
        </Section>
      )}

      <Section title="Cuentas" id="adm-users" aside={data && <span className="text-[13.5px] text-text-3" data-num>{data.users.total} en total</span>}>
        {users.isPending ? (
          <Skeleton className="h-40 !rounded-[22px]" />
        ) : (
          <ul className="card overflow-hidden">
            {accounts.map((user) => (
              <li key={user.id} className="border-b border-border last:border-b-0">
                <button type="button" onClick={() => setSelected(user)} className="flex min-h-[60px] w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-surface-2">
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 text-[15px] font-medium text-text">
                      <span className="truncate">{user.username}</span>
                      {user.is_admin && <span className="shrink-0 text-[12px] font-semibold text-accent-text">tú · admin</span>}
                    </p>
                    <p className="mt-0.5 text-[12.5px] text-text-3" data-num>
                      IA {user.today.ai}/{user.limits.ai} · voz {user.today.stt}/{user.limits.stt} hoy
                    </p>
                  </div>
                  <StatusChip status={user.status} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Actividad" id="adm-audit">
        {audit.data && audit.data.length > 0 ? (
          <ol className="card divide-y divide-border">
            {audit.data.map((entry) => (
              <AuditRow key={entry.id} entry={entry} />
            ))}
          </ol>
        ) : (
          <div className="card">
            <EmptyState art="book" title="Sin actividad todavía" text="Cada aprobación, bloqueo o cambio de límites quedará apuntado aquí." compact />
          </div>
        )}
      </Section>

      <UserSheet user={selected} onClose={() => setSelected(null)} act={act} busy={busy} />
    </main>
  )
}

function BackupCard({ backup }: { backup: BackupStatus }) {
  if (!backup.configured) {
    return (
      <div className="card p-4 text-[14px] leading-relaxed text-text-2">
        Solo hay copia local: cada noche, las {backup.local_keep} últimas en el propio servidor. Para tener una copia fuera
        (S3, R2, B2…) configura las variables <code>BACKUP_REMOTE_*</code>: está explicado en el README.
      </div>
    )
  }
  const failed = backup.ok === false
  return (
    <div className="card space-y-2 p-4">
      {failed && (
        <Notice level="danger">
          La última subida falló{backup.attempts ? ` (${backup.attempts} ${plural(backup.attempts, 'intento', 'intentos')})` : ''}: {backup.error}
        </Notice>
      )}
      <p className="text-[14px] text-text-2" data-num>
        {backup.ok
          ? `Última copia externa ${fmtAgo(backup.at)}${backup.size ? `, ${fmt(backup.size / 1024)} KB` : ''}.`
          : backup.last_ok_at
            ? `La última que salió bien fue ${fmtAgo(backup.last_ok_at)}.`
            : 'Todavía no se ha subido ninguna copia.'}{' '}
        Se guardan las {backup.remote_keep} más recientes{backup.encrypted ? ', cifradas' : ', sin cifrar'}.
      </p>
    </div>
  )
}

function AuditRow({ entry }: { entry: AuditEntry }) {
  const details = Object.entries(entry.details ?? {})
    .map(([key, value]) => `${key}: ${value === null ? 'por defecto' : String(value)}`)
    .join(', ')
  return (
    <li className="px-4 py-2.5">
      <p className="text-[14px] text-text">
        <span className="font-semibold">{entry.admin}</span> {ACTIONS[entry.action] ?? entry.action} {entry.target && <span className="font-semibold">{entry.target}</span>}
      </p>
      <p className="mt-0.5 text-[12.5px] text-text-3">
        {fmtAgo(entry.created_at)}
        {details && ` · ${details}`}
      </p>
    </li>
  )
}

interface UserSheetProps {
  user: AdminUser | null
  onClose: () => void
  act: (key: string, run: () => Promise<unknown>, success: string) => Promise<void>
  busy: string | null
}

function UserSheet({ user, onClose, act, busy }: UserSheetProps) {
  const [shown, setShown] = useState<AdminUser | null>(null)
  const [ai, setAi] = useState<number | null>(null)
  const [stt, setStt] = useState<number | null>(null)
  const [confirm, setConfirm] = useState('')
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (!user) return
    setShown(user)
    setAi(user.limits.ai_custom)
    setStt(user.limits.stt_custom)
    setConfirm('')
    setDeleting(false)
  }, [user])

  const current = user ?? shown
  const run = async (key: string, call: () => Promise<unknown>, message: string, close = false) => {
    await act(key, call, message)
    if (close) onClose()
  }

  return (
    <Sheet open={!!user} onClose={onClose} title={current ? current.username : 'Cuenta'}>
      {current && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2 text-[13.5px] text-text-2">
            <StatusChip status={current.status} />
            <span>Alta {fmtAgo(current.created_at)}</span>
            <span aria-hidden>·</span>
            <span>Último acceso {fmtAgo(current.last_seen_at)}</span>
          </div>

          <dl className="grid grid-cols-2 gap-2.5">
            {[
              ['IA hoy', `${current.today.ai} de ${current.limits.ai}`],
              ['Voz hoy', `${current.today.stt} de ${current.limits.stt}`],
              ['IA este mes', `${current.month.ai} consultas`],
              ['Coste este mes', money(current.month.cost)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-md bg-surface-2 px-3 py-2.5">
                <dt className="text-[12.5px] text-text-3">{label}</dt>
                <dd className="mt-0.5 text-[16px] font-semibold text-text" data-num>{value}</dd>
              </div>
            ))}
          </dl>

          <div>
            <h3 className="text-[15px] font-semibold text-text">Límites diarios</h3>
            <p className="mt-0.5 text-[13px] text-text-3">Vacío = el valor por defecto de la instalación.</p>
            <div className="mt-2.5 grid grid-cols-2 gap-2.5">
              {(
                [
                  ['Consultas de IA', ai, setAi],
                  ['Audios', stt, setStt],
                ] as const
              ).map(([label, value, set]) => (
                <label key={label} className="block rounded-md border border-border bg-surface-2 px-3 py-2 focus-within:border-accent">
                  <span className="block text-[12.5px] text-text-3">{label}</span>
                  <NumberInput value={value} onChange={set} decimals={0} min={0} max={10000} ariaLabel={`${label} al día`} placeholder="Por defecto" className="mt-0.5 w-full text-[17px] font-semibold text-text" />
                </label>
              ))}
            </div>
            <Button
              variant="secondary"
              size="sm"
              block
              className="mt-2.5"
              loading={busy === 'limits'}
              disabled={ai === current.limits.ai_custom && stt === current.limits.stt_custom}
              onClick={() => void run('limits', () => api.patch(`/api/admin/users/${current.id}/limits`, { ai_daily_limit: ai, stt_daily_limit: stt }), 'Límites guardados')}
              icon={<KeyRound className="size-4" aria-hidden />}
            >
              Guardar límites
            </Button>
          </div>

          {!current.is_admin && (
            <div className="grid grid-cols-2 gap-2.5">
              {current.status === 'suspended' ? (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={busy === 'unsuspend'}
                  onClick={() => void run('unsuspend', () => api.post(`/api/admin/users/${current.id}/unsuspend`), `${current.username} desbloqueada`, true)}
                  icon={<UserCheck className="size-4" aria-hidden />}
                >
                  Desbloquear
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={busy === 'suspend'}
                  onClick={() => void run('suspend', () => api.post(`/api/admin/users/${current.id}/suspend`), `${current.username} bloqueada`, true)}
                  icon={<Ban className="size-4" aria-hidden />}
                >
                  Bloquear
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                loading={busy === 'logout'}
                disabled={current.sessions === 0}
                onClick={() => void run('logout', () => api.post(`/api/admin/users/${current.id}/logout-all`), 'Sesiones cerradas')}
                icon={<LogOut className="size-4" aria-hidden />}
              >
                Cerrar sesiones
              </Button>
            </div>
          )}

          {!current.is_admin &&
            (deleting ? (
              <div className="rounded-md bg-danger-soft p-3.5">
                <p className="text-[14px] leading-relaxed text-text">
                  Se borrarán la cuenta y todos sus datos. No se puede deshacer. Escribe <strong>{current.username}</strong> para confirmar.
                </p>
                <Field label="Nombre de la cuenta" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoCapitalize="none" autoCorrect="off" className="mt-3" />
                <div className="mt-3 grid grid-cols-2 gap-2.5">
                  <Button variant="secondary" size="sm" onClick={() => setDeleting(false)}>
                    Cancelar
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    loading={busy === 'delete'}
                    disabled={confirm.trim().toLowerCase() !== current.username.toLowerCase()}
                    onClick={() => void run('delete', () => api.post(`/api/admin/users/${current.id}/delete`, { confirm }), `Cuenta de ${current.username} eliminada`, true)}
                    icon={<Trash2 className="size-4" aria-hidden />}
                  >
                    Eliminar
                  </Button>
                </div>
              </div>
            ) : (
              <Button variant="danger" size="sm" block onClick={() => setDeleting(true)} icon={<Trash2 className="size-4" aria-hidden />}>
                Eliminar la cuenta y sus datos
              </Button>
            ))}
          {current.is_admin && <Notice level="info">Es tu cuenta: no puedes bloquearla ni eliminarla desde aquí.</Notice>}
        </div>
      )}
    </Sheet>
  )
}

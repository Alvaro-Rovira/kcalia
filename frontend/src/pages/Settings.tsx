import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  ChevronRight,
  Download,
  FileJson,
  FileSpreadsheet,
  LogOut,
  Monitor,
  Moon,
  Pencil,
  PlusSquare,
  RefreshCw,
  Share,
  Smartphone,
  Sun,
  Trash2,
  Zap,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Logo, Wordmark } from '@/components/Logo'
import { PlanExplanation } from '@/components/PlanExplanation'
import { useApp, useOnline, useStats } from '@/hooks/data'
import { useInstall } from '@/hooks/useInstall'
import { api, errorMessage } from '@/lib/api'
import { fmt, kgTo, toKg } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { GRAM_MACROS, KCAL_PER_GRAM, MACROS } from '@/lib/macros'
import { ACTIVITIES, ACTIVITY_LABEL, GOAL_LABEL, GOALS } from '@/lib/options'
import { getThemePref, setThemePref } from '@/lib/theme'
import type { Activity, Bootstrap, Goal, Plan, Profile, Sex, Targets, ThemePref, Warning } from '@/lib/types'
import { clearOutbox } from '@/offline/outbox'
import { clearLocalData, keys } from '@/offline/queryClient'
import { AnimatedNumber } from '@/ui/AnimatedNumber'
import { Button } from '@/ui/Button'
import { Field, NumberInput } from '@/ui/Field'
import { Notice } from '@/ui/Notice'
import { Segmented } from '@/ui/Segmented'
import { Sheet } from '@/ui/Sheet'
import { toast } from '@/ui/toast'

function Section({ title, children, id }: { title: string; children: ReactNode; id: string }) {
  return (
    <section className="mt-6" aria-labelledby={id}>
      <h2 id={id} className="eyebrow px-1">
        {title}
      </h2>
      <div className="card mt-2 overflow-hidden">{children}</div>
    </section>
  )
}

function Row({ label, value, onClick, icon, danger }: { label: string; value?: ReactNode; onClick?: () => void; icon?: ReactNode; danger?: boolean }) {
  const content = (
    <>
      {icon && <span className={clsx('shrink-0', danger ? 'text-danger-text' : 'text-text-3')}>{icon}</span>}
      <span className={clsx('min-w-0 flex-1 text-[15px]', danger ? 'font-medium text-danger-text' : 'text-text')}>{label}</span>
      {value !== undefined && (
        <span className="shrink-0 text-[14.5px] text-text-2" data-num>
          {value}
        </span>
      )}
      {onClick && !danger && <ChevronRight className="size-4 shrink-0 text-text-3" aria-hidden />}
    </>
  )
  const className = 'flex min-h-[52px] w-full items-center gap-3 border-b border-border px-4 py-2.5 text-left last:border-b-0'
  return onClick ? (
    <button type="button" onClick={onClick} className={clsx(className, 'transition-colors hover:bg-surface-2')}>
      {content}
    </button>
  ) : (
    <div className={className}>{content}</div>
  )
}

export default function Settings() {
  const app = useApp()
  const { profile, targets } = app
  const stats = useStats()
  const client = useQueryClient()
  const online = useOnline()
  const install = useInstall()
  const [theme, setTheme] = useState<ThemePref>(getThemePref)
  const [sheet, setSheet] = useState<'profile' | 'targets' | 'plan' | 'delete-data' | 'delete-account' | null>(null)
  const unit = profile.weight_unit

  async function setUnit(next: 'kg' | 'lb') {
    client.setQueryData<Bootstrap>(keys.bootstrap, (old) => (old?.profile ? { ...old, profile: { ...old.profile, weight_unit: next } } : old))
    try {
      await api.patch('/api/profile/prefs', { weight_unit: next })
    } catch (error) {
      toast.error('No se ha podido guardar la unidad', errorMessage(error))
      void client.invalidateQueries({ queryKey: keys.bootstrap })
    }
  }

  async function recalculate() {
    try {
      await api.post('/api/targets/recalculate')
      await client.invalidateQueries({ queryKey: keys.bootstrap })
      void client.invalidateQueries({ queryKey: keys.weight })
      haptic('success')
      toast.success('Objetivos recalculados', 'Con tu perfil y tu peso actuales.')
    } catch (error) {
      toast.error('No se han podido recalcular', errorMessage(error))
    }
  }

  async function logout() {
    try {
      await api.post('/api/auth/logout')
    } catch {
      // Sin red también se cierra: se borra todo lo guardado en este dispositivo.
    }
    await clearOutbox()
    await clearLocalData()
    window.location.assign('/')
  }

  const saved = stats.data?.ai

  return (
    <main className="page">
      <header>
        <h1 className="text-[30px] leading-tight font-semibold tracking-[-0.035em] text-text">Ajustes</h1>
        <p className="mt-1 text-[14.5px] text-text-2">Sesión iniciada como {app.user.username}</p>
      </header>

      <div className="lg:grid lg:grid-cols-2 lg:gap-x-6">
        <div>
          <Section title="Perfil" id="a-profile">
            <Row label="Sexo" value={profile.sex === 'hombre' ? 'Hombre' : 'Mujer'} />
            <Row label="Edad" value={`${profile.age} años`} />
            <Row label="Altura" value={`${fmt(profile.height_cm)} cm`} />
            <Row label="Peso" value={`${fmt(kgTo(unit, profile.weight_kg), 1)} ${unit}`} />
            <Row label="Actividad" value={ACTIVITY_LABEL[profile.activity]} />
            <Row label="Objetivo" value={GOAL_LABEL[profile.goal]} />
            <Row label="Peso objetivo" value={profile.target_weight_kg === null ? 'Sin definir' : `${fmt(kgTo(unit, profile.target_weight_kg), 1)} ${unit}`} />
            <Row label="Editar perfil" onClick={() => setSheet('profile')} icon={<Pencil className="size-[18px]" aria-hidden />} />
          </Section>

          <Section title="Objetivos diarios" id="a-targets">
            <div className="grid grid-cols-4 divide-x divide-border border-b border-border">
              {[MACROS.kcal, ...GRAM_MACROS].map((m) => (
                <div key={m.key} className="px-1 py-3.5 text-center">
                  <p className="flex items-center justify-center gap-1 text-[11.5px] font-semibold" style={{ color: m.text }}>
                    <m.Icon className="size-3.5" aria-hidden />
                    {m.key === 'kcal' ? 'kcal' : m.letter}
                    <span className="sr-only">{m.label}</span>
                  </p>
                  <p className="mt-1 text-[19px] leading-none font-semibold tracking-[-0.02em] text-text" data-num>
                    {fmt(targets[m.key])}
                    {m.key !== 'kcal' && <span className="ml-0.5 text-[12px] font-medium text-text-3">g</span>}
                  </p>
                </div>
              ))}
            </div>
            {targets.custom && (
              <div className="border-b border-border px-4 py-2.5 text-[13px] text-text-3">Objetivos ajustados a mano. Al recalcular se sustituyen por los del plan.</div>
            )}
            <Row label="Cómo se calculan" onClick={() => setSheet('plan')} />
            <Row label="Editar a mano" onClick={() => setSheet('targets')} icon={<Pencil className="size-[18px]" aria-hidden />} />
            <Row label="Recalcular con mi perfil" onClick={() => void recalculate()} icon={<RefreshCw className="size-[18px]" aria-hidden />} />
          </Section>
        </div>

        <div>
          <Section title="Apariencia y unidades" id="a-look">
            <div className="border-b border-border p-3">
              <Segmented
                label="Tema"
                value={theme}
                onChange={(next) => {
                  setTheme(next)
                  setThemePref(next)
                }}
                options={[
                  { value: 'dark', label: <><Moon className="size-4" aria-hidden /> Oscuro</> },
                  { value: 'light', label: <><Sun className="size-4" aria-hidden /> Claro</> },
                  { value: 'auto', label: <><Monitor className="size-4" aria-hidden /> Auto</> },
                ]}
              />
            </div>
            <div className="flex items-center justify-between gap-3 px-4 py-2.5">
              <span className="text-[15px] text-text">Unidad de peso</span>
              <Segmented
                label="Unidad de peso"
                size="sm"
                className="w-[132px]"
                value={unit}
                onChange={(next) => void setUnit(next)}
                options={[
                  { value: 'kg', label: 'kg' },
                  { value: 'lb', label: 'lb' },
                ]}
              />
            </div>
          </Section>

          <Section title="Inteligencia artificial" id="a-ai">
            <div className="flex items-center gap-3.5 border-b border-border p-4">
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-soft text-accent-text">
                <Zap className="size-5" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[24px] leading-none font-semibold tracking-[-0.03em] text-text">
                  <AnimatedNumber value={saved?.saved_total ?? 0} />
                </p>
                <p className="mt-1 text-[13.5px] text-text-2">consultas a la IA ahorradas</p>
              </div>
            </div>
            {saved && saved.saved_total > 0 && (
              <>
                <Row label="Del historial, texto idéntico" value={saved.saved.saved_exact} />
                <Row label="Del historial, texto parecido" value={saved.saved.saved_fuzzy} />
                <Row label="Con ingredientes conocidos" value={saved.saved.saved_cache} />
                <Row label="Con tus productos guardados" value={saved.saved.saved_product ?? 0} />
                <Row label="Favoritos y recientes, a un toque" value={saved.saved.saved_quick} />
              </>
            )}
            <Row label="Consultas de hoy" value={`${saved?.used_today ?? app.ai.used_today} de ${app.ai.limit}`} />
            <Row label="Modelo" value={app.ai.configured ? app.ai.model : 'Sin configurar'} />
          </Section>

          {!install.installed && (
            <Section title="Instalar como app" id="a-install">
              {install.canPrompt ? (
                <Row label="Instalar Kcalia en este dispositivo" onClick={() => void install.prompt()} icon={<Smartphone className="size-[18px]" aria-hidden />} />
              ) : (
                <div className="p-4 text-[14px] leading-relaxed text-text-2">
                  {install.ios ? (
                    <ol className="space-y-2">
                      <li className="flex items-center gap-2.5">
                        <Share className="size-[18px] shrink-0 text-accent-text" aria-hidden /> En Safari, pulsa <strong className="font-semibold text-text">Compartir</strong>.
                      </li>
                      <li className="flex items-center gap-2.5">
                        <PlusSquare className="size-[18px] shrink-0 text-accent-text" aria-hidden /> Elige{' '}
                        <strong className="font-semibold text-text">Añadir a pantalla de inicio</strong>.
                      </li>
                    </ol>
                  ) : (
                    <p>
                      Abre el menú del navegador y elige <strong className="font-semibold text-text">Instalar aplicación</strong> o{' '}
                      <strong className="font-semibold text-text">Añadir a pantalla de inicio</strong>.
                    </p>
                  )}
                </div>
              )}
            </Section>
          )}

          <Section title="Tus datos" id="a-data">
            <a href="/api/export/json" download="kcalia-datos.json" className="flex min-h-[52px] items-center gap-3 border-b border-border px-4 py-2.5 transition-colors hover:bg-surface-2">
              <FileJson className="size-[18px] shrink-0 text-text-3" aria-hidden />
              <span className="flex-1 text-[15px] text-text">Exportar todo (JSON)</span>
              <Download className="size-4 text-text-3" aria-hidden />
            </a>
            <a href="/api/export/meals.csv" download className="flex min-h-[52px] items-center gap-3 border-b border-border px-4 py-2.5 transition-colors hover:bg-surface-2">
              <FileSpreadsheet className="size-[18px] shrink-0 text-text-3" aria-hidden />
              <span className="flex-1 text-[15px] text-text">Exportar comidas (CSV)</span>
              <Download className="size-4 text-text-3" aria-hidden />
            </a>
            <a href="/api/export/weights.csv" download className="flex min-h-[52px] items-center gap-3 px-4 py-2.5 transition-colors hover:bg-surface-2">
              <FileSpreadsheet className="size-[18px] shrink-0 text-text-3" aria-hidden />
              <span className="flex-1 text-[15px] text-text">Exportar peso (CSV)</span>
              <Download className="size-4 text-text-3" aria-hidden />
            </a>
          </Section>

          <Section title="Cuenta" id="a-account">
            <Row label="Cerrar sesión" onClick={() => void logout()} icon={<LogOut className="size-[18px]" aria-hidden />} />
            <Row label="Borrar mis datos" onClick={() => setSheet('delete-data')} icon={<Trash2 className="size-[18px]" aria-hidden />} danger />
            <Row label="Borrar mi cuenta" onClick={() => setSheet('delete-account')} icon={<Trash2 className="size-[18px]" aria-hidden />} danger />
          </Section>
        </div>
      </div>

      <footer className="mt-9 flex flex-col items-center gap-2 text-center">
        <div className="flex items-center gap-2">
          <Logo size={24} />
          <Wordmark className="text-[17px]" />
        </div>
        <p className="text-[12.5px] text-text-3">
          Versión {__APP_VERSION__} ·{' '}
          <a href={__REPO_URL__} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-text-2">
            Código en GitHub
          </a>
        </p>
        {!online && <p className="text-[12.5px] text-warn-text">Sin conexión: los cambios de ajustes necesitan red.</p>}
      </footer>

      <ProfileSheet open={sheet === 'profile'} onClose={() => setSheet(null)} profile={profile} />
      <TargetsSheet open={sheet === 'targets'} onClose={() => setSheet(null)} targets={targets} />
      <Sheet open={sheet === 'plan'} onClose={() => setSheet(null)} title="Tu plan">
        {app.plan && (
          <div className="space-y-3">
            {app.plan.warnings.map((warning) => (
              <Notice key={warning.code} level={warning.level}>
                {warning.text}
              </Notice>
            ))}
            <PlanExplanation plan={app.plan} targetWeight={profile.target_weight_kg} />
          </div>
        )}
      </Sheet>
      <DeleteSheet kind={sheet === 'delete-data' ? 'data' : sheet === 'delete-account' ? 'account' : null} onClose={() => setSheet(null)} />
    </main>
  )
}

function SelectField<T extends string>({ label, value, onChange, options }: { label: string; value: T; onChange: (value: T) => void; options: { value: T; label: string }[] }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13.5px] font-medium text-text-2">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
        className="h-13 w-full appearance-none rounded-md border border-border bg-surface-2 px-4 text-text outline-none focus:border-accent"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function NumberField({ label, value, onChange, suffix, decimals = 0, min, max }: { label: string; value: number | null; onChange: (value: number | null) => void; suffix: string; decimals?: number; min: number; max: number }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13.5px] font-medium text-text-2">{label}</span>
      <span className="flex h-13 items-center rounded-md border border-border bg-surface-2 px-4 focus-within:border-accent">
        <NumberInput value={value} onChange={onChange} decimals={decimals} min={min} max={max} ariaLabel={label} className="h-full min-w-0 flex-1 text-text" />
        <span className="ml-2 text-[14px] text-text-3">{suffix}</span>
      </span>
    </label>
  )
}

function ProfileSheet({ open, onClose, profile }: { open: boolean; onClose: () => void; profile: Profile }) {
  const client = useQueryClient()
  const unit = profile.weight_unit
  const [sex, setSex] = useState<Sex>(profile.sex)
  const [age, setAge] = useState<number | null>(profile.age)
  const [height, setHeight] = useState<number | null>(profile.height_cm)
  const [weight, setWeight] = useState<number | null>(Number(kgTo(unit, profile.weight_kg).toFixed(1)))
  const [activity, setActivity] = useState<Activity>(profile.activity)
  const [goal, setGoal] = useState<Goal>(profile.goal)
  const [target, setTarget] = useState<number | null>(profile.target_weight_kg === null ? null : Number(kgTo(unit, profile.target_weight_kg).toFixed(1)))
  const [busy, setBusy] = useState(false)

  // Al abrir, el formulario parte siempre de lo guardado.
  useEffect(() => {
    if (!open) return
    setSex(profile.sex)
    setAge(profile.age)
    setHeight(profile.height_cm)
    setWeight(Number(kgTo(unit, profile.weight_kg).toFixed(1)))
    setActivity(profile.activity)
    setGoal(profile.goal)
    setTarget(profile.target_weight_kg === null ? null : Number(kgTo(unit, profile.target_weight_kg).toFixed(1)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const valid = age !== null && age >= 14 && age <= 100 && height !== null && height >= 120 && height <= 230 && weight !== null && toKg(unit, weight) >= 30 && toKg(unit, weight) <= 300

  async function save() {
    if (!valid || busy) return
    setBusy(true)
    try {
      const saved = await api.put<{ profile: Profile; targets: Targets; plan: Plan }>('/api/profile', {
        sex,
        age,
        height_cm: height,
        weight_kg: Number(toKg(unit, weight!).toFixed(2)),
        activity,
        goal,
        target_weight_kg: target === null ? null : Number(toKg(unit, target).toFixed(2)),
        recalculate: true,
      })
      client.setQueryData<Bootstrap>(keys.bootstrap, (old) => (old ? { ...old, ...saved } : old))
      void client.invalidateQueries()
      haptic('success')
      toast.success('Perfil guardado', `Objetivo actualizado: ${fmt(saved.targets.kcal)} kcal al día.`)
      onClose()
    } catch (error) {
      toast.error('No se ha podido guardar', errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Editar perfil"
      footer={
        <Button size="lg" block onClick={save} loading={busy} disabled={!valid}>
          Guardar y recalcular objetivos
        </Button>
      }
    >
      <div className="space-y-4 pt-2">
        <div>
          <span className="mb-1.5 block text-[13.5px] font-medium text-text-2">Sexo</span>
          <Segmented
            label="Sexo"
            value={sex}
            onChange={setSex}
            options={[
              { value: 'hombre', label: 'Hombre' },
              { value: 'mujer', label: 'Mujer' },
            ]}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <NumberField label="Edad" value={age} onChange={setAge} suffix="años" min={14} max={100} />
          <NumberField label="Altura" value={height} onChange={setHeight} suffix="cm" min={120} max={230} />
          <NumberField label="Peso" value={weight} onChange={setWeight} suffix={unit} decimals={1} min={unit === 'lb' ? 66 : 30} max={unit === 'lb' ? 660 : 300} />
          <NumberField label="Peso objetivo" value={target} onChange={setTarget} suffix={unit} decimals={1} min={unit === 'lb' ? 66 : 30} max={unit === 'lb' ? 660 : 300} />
        </div>
        <SelectField label="Nivel de actividad" value={activity} onChange={setActivity} options={ACTIVITIES.map((a) => ({ value: a.value, label: `${a.label} · ${a.text}` }))} />
        <SelectField label="Objetivo" value={goal} onChange={setGoal} options={GOALS.map((g) => ({ value: g.value, label: `${g.label} (${g.tag})` }))} />
        <p className="text-[13px] leading-relaxed text-text-3">Deja el peso objetivo vacío si no quieres usarlo.</p>
      </div>
    </Sheet>
  )
}

function TargetsSheet({ open, onClose, targets }: { open: boolean; onClose: () => void; targets: Targets }) {
  const client = useQueryClient()
  const [kcal, setKcal] = useState<number | null>(targets.kcal)
  const [protein, setProtein] = useState<number | null>(targets.protein)
  const [carbs, setCarbs] = useState<number | null>(targets.carbs)
  const [fat, setFat] = useState<number | null>(targets.fat)
  const [busy, setBusy] = useState(false)
  const [warnings, setWarnings] = useState<Warning[]>([])

  useEffect(() => {
    if (!open) return
    setKcal(targets.kcal)
    setProtein(targets.protein)
    setCarbs(targets.carbs)
    setFat(targets.fat)
    setWarnings([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const complete = kcal !== null && protein !== null && carbs !== null && fat !== null
  const fromMacros = complete ? protein * KCAL_PER_GRAM.protein + carbs * KCAL_PER_GRAM.carbs + fat * KCAL_PER_GRAM.fat : 0
  const mismatch = complete ? fromMacros - kcal : 0
  const valid = complete && kcal >= 800 && kcal <= 8000 && protein >= 20 && fat >= 10

  async function save() {
    if (!valid || busy) return
    setBusy(true)
    try {
      const result = await api.put<{ targets: Targets; warnings: Warning[] }>('/api/targets', { kcal, protein, carbs, fat })
      client.setQueryData<Bootstrap>(keys.bootstrap, (old) => (old ? { ...old, targets: result.targets } : old))
      void client.invalidateQueries()
      haptic('success')
      if (result.warnings.length) {
        setWarnings(result.warnings)
        toast.success('Objetivos guardados', 'Revisa el aviso antes de cerrar.')
      } else {
        toast.success('Objetivos guardados')
        onClose()
      }
    } catch (error) {
      toast.error('No se han podido guardar', errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet
      open={open}
      onClose={() => {
        setWarnings([])
        onClose()
      }}
      title="Objetivos a mano"
      footer={
        <Button size="lg" block onClick={save} loading={busy} disabled={!valid}>
          Guardar objetivos
        </Button>
      }
    >
      <div className="space-y-4 pt-2">
        <NumberField label="Calorías" value={kcal} onChange={setKcal} suffix="kcal" min={800} max={8000} />
        <div className="grid grid-cols-3 gap-3">
          <NumberField label="Proteínas" value={protein} onChange={setProtein} suffix="g" min={20} max={500} />
          <NumberField label="Hidratos" value={carbs} onChange={setCarbs} suffix="g" min={0} max={1200} />
          <NumberField label="Grasas" value={fat} onChange={setFat} suffix="g" min={10} max={400} />
        </div>
        {complete && (
          <div className="rounded-md bg-surface-2 p-3.5 text-[13.5px] leading-relaxed text-text-2" data-num>
            Tus macros suman <strong className="font-semibold text-text">{fmt(fromMacros)} kcal</strong>
            {Math.abs(mismatch) > 50 ? (
              <>
                , {fmt(Math.abs(mismatch))} kcal {mismatch > 0 ? 'más' : 'menos'} que el objetivo.{' '}
                <button type="button" onClick={() => setKcal(Math.round(fromMacros / 10) * 10)} className="min-h-11 font-semibold text-accent-text underline underline-offset-2">
                  Igualar calorías
                </button>
              </>
            ) : (
              ': cuadran con el objetivo.'
            )}
          </div>
        )}
        {warnings.map((warning) => (
          <Notice key={warning.code} level={warning.level}>
            {warning.text}
          </Notice>
        ))}
      </div>
    </Sheet>
  )
}

function DeleteSheet({ kind, onClose }: { kind: 'data' | 'account' | null; onClose: () => void }) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [shown, setShown] = useState<'data' | 'account'>('data')
  if (kind && kind !== shown) setShown(kind)
  const account = (kind ?? shown) === 'account'

  async function confirm() {
    if (!password || busy) return
    setBusy(true)
    setError('')
    try {
      await api.post(account ? '/api/account/delete' : '/api/data/delete', { password })
      await clearOutbox()
      await clearLocalData()
      window.location.assign('/')
    } catch (err) {
      setError(errorMessage(err))
      haptic('error')
      setBusy(false)
    }
  }

  return (
    <Sheet
      open={!!kind}
      onClose={() => {
        setPassword('')
        setError('')
        onClose()
      }}
      title={account ? 'Borrar mi cuenta' : 'Borrar mis datos'}
      footer={
        <Button size="lg" block variant="danger" onClick={confirm} loading={busy} disabled={!password}>
          {account ? 'Borrar cuenta y datos para siempre' : 'Borrar todos mis datos'}
        </Button>
      }
    >
      <div className="space-y-4 pt-1">
        <Notice level="danger">
          {account
            ? 'Se borrarán tu cuenta, tu diario, tu peso y tu historial. El registro quedará abierto de nuevo. No se puede deshacer.'
            : 'Se borrarán tu diario, tu peso, tu historial de comidas y tu perfil. La cuenta se conserva. No se puede deshacer.'}
        </Notice>
        <p className="text-[14px] leading-relaxed text-text-2">Si quieres conservar una copia, expórtala antes desde «Tus datos».</p>
        <Field
          label="Escribe tu contraseña para confirmar"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={error || undefined}
        />
      </div>
    </Sheet>
  )
}

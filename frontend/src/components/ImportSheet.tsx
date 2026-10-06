import { useQueryClient } from '@tanstack/react-query'
import { FileUp } from 'lucide-react'
import { useRef, useState } from 'react'
import { useOnline } from '@/hooks/data'
import { api, errorMessage } from '@/lib/api'
import { fmtMedium } from '@/lib/dates'
import { fmt } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { SLOT_BY_KEY } from '@/lib/slots'
import type { Slot } from '@/lib/types'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { Sheet } from '@/ui/Sheet'
import { Switch } from '@/ui/Switch'
import { toast } from '@/ui/toast'

type Field = 'date' | 'slot' | 'name' | 'kcal' | 'protein' | 'carbs' | 'fat' | 'fiber' | 'grams'
type Mapping = Record<Field, string | null>

interface Preview {
  format: 'myfitnesspal' | 'yazio' | 'generico'
  columns: string[]
  mapping: Mapping
  rows: number
  valid: number
  new: number
  already: number
  duplicates: number
  errors: { line: number; message: string }[]
  error_count: number
  sample: { date: string; slot: Slot; name: string; kcal: number; protein: number; carbs: number; fat: number }[]
}

const FIELDS: { key: Field; label: string; required?: boolean }[] = [
  { key: 'date', label: 'Fecha', required: true },
  { key: 'kcal', label: 'Calorías', required: true },
  { key: 'slot', label: 'Momento del día' },
  { key: 'name', label: 'Nombre' },
  { key: 'protein', label: 'Proteína (g)' },
  { key: 'carbs', label: 'Hidratos (g)' },
  { key: 'fat', label: 'Grasa (g)' },
  { key: 'fiber', label: 'Fibra (g)' },
  { key: 'grams', label: 'Gramos' },
]

const FORMAT_LABEL: Record<Preview['format'], string> = {
  myfitnesspal: 'Exportación de MyFitnessPal',
  yazio: 'Exportación de Yazio',
  generico: 'CSV genérico',
}

const COUNT_LABEL: Record<string, string> = {
  plan: 'comidas planificadas',
  'tipos de día': 'días marcados',
  agua: 'registros de agua',
}

function form(file: File, extra: Record<string, string> = {}) {
  const data = new FormData()
  data.append('file', file)
  for (const [key, value] of Object.entries(extra)) data.append(key, value)
  return data
}

/** Importar comidas desde otra app (CSV) o restaurar una exportación de Kcalia (JSON). Necesita conexión. */
export function ImportSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const client = useQueryClient()
  const online = useOnline()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [mapping, setMapping] = useState<Mapping | null>(null)
  const [monthFirst, setMonthFirst] = useState(false)
  const [skipDuplicates, setSkipDuplicates] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function reset() {
    setFile(null)
    setPreview(null)
    setMapping(null)
    setMonthFirst(false)
    setSkipDuplicates(true)
    setError('')
    if (input.current) input.current.value = ''
  }

  async function refresh() {
    await client.invalidateQueries()
  }

  async function loadPreview(chosen: File, nextMapping: Mapping | null, nextMonthFirst: boolean) {
    setBusy(true)
    setError('')
    try {
      const extra: Record<string, string> = { month_first: String(nextMonthFirst) }
      if (nextMapping) extra.mapping = JSON.stringify(nextMapping)
      const result = await api.post<Preview>('/api/import/csv/preview', form(chosen, extra))
      setPreview(result)
      setMapping(result.mapping)
    } catch (err) {
      setPreview(null)
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function pick(chosen: File | undefined) {
    if (!chosen) return
    setFile(chosen)
    setPreview(null)
    setMapping(null)
    if (chosen.name.toLowerCase().endsWith('.json')) return
    await loadPreview(chosen, null, monthFirst)
  }

  async function importJson() {
    if (!file) return
    setBusy(true)
    setError('')
    try {
      const { created } = await api.post<{ created: Record<string, number> }>('/api/import/json', form(file))
      const parts = Object.entries(created)
        .filter(([, n]) => n > 0)
        .map(([key, n]) => `${fmt(n)} ${COUNT_LABEL[key] ?? key}`)
      await refresh()
      haptic('success')
      toast.success('Datos importados', parts.length ? parts.join(', ') : 'No había nada nuevo que añadir.')
      reset()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  async function importCsv() {
    if (!file || !mapping) return
    setBusy(true)
    setError('')
    try {
      const result = await api.post<{ created: number; already: number; skipped_duplicates: number; errors: number }>(
        '/api/import/csv',
        form(file, { mapping: JSON.stringify(mapping), month_first: String(monthFirst), skip_duplicates: String(skipDuplicates) }),
      )
      await refresh()
      haptic('success')
      const extra = [
        result.already ? `${fmt(result.already)} ya estaban` : '',
        result.skipped_duplicates ? `${fmt(result.skipped_duplicates)} parecidas saltadas` : '',
      ].filter(Boolean)
      toast.success(`${fmt(result.created)} ${result.created === 1 ? 'comida importada' : 'comidas importadas'}`, extra.join(' · ') || undefined)
      reset()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  const isJson = !!file && file.name.toLowerCase().endsWith('.json')
  const missing = mapping ? FIELDS.filter((f) => f.required && !mapping[f.key]) : []
  const toImport = preview ? preview.new + (skipDuplicates ? 0 : preview.duplicates) : 0

  return (
    <Sheet
      open={open}
      onClose={() => {
        reset()
        onClose()
      }}
      title="Importar datos"
      tall
      footer={
        file && (isJson || preview) ? (
          <Button
            size="lg"
            block
            onClick={isJson ? importJson : importCsv}
            loading={busy}
            disabled={!online || (!isJson && (missing.length > 0 || toImport === 0))}
          >
            {isJson ? 'Importar copia de Kcalia' : toImport === 0 ? 'Nada nuevo que importar' : `Importar ${fmt(toImport)} ${toImport === 1 ? 'comida' : 'comidas'}`}
          </Button>
        ) : undefined
      }
    >
      <div className="space-y-4 pt-1">
        <p className="text-[14px] leading-relaxed text-text-2">
          Trae tus comidas desde MyFitnessPal, Yazio u otra app (exportación en CSV), o restaura una copia de Kcalia (JSON). Importar dos veces el mismo
          fichero no duplica nada.
        </p>
        {!online && <Notice level="warn">Importar necesita conexión.</Notice>}

        <input
          ref={input}
          type="file"
          accept=".csv,.json,.txt,text/csv,application/json"
          className="sr-only"
          aria-label="Fichero para importar"
          onChange={(event) => void pick(event.target.files?.[0])}
        />
        <Button variant="secondary" block onClick={() => input.current?.click()} disabled={!online || busy}>
          <FileUp className="size-4" aria-hidden />
          {file ? `Cambiar fichero (${file.name})` : 'Elegir fichero CSV o JSON'}
        </Button>

        {error && <Notice level="danger">{error}</Notice>}

        {isJson && (
          <Notice level="info">
            Se añadirá lo que no tengas ya: comidas, peso, agua, medidas, entrenos, productos y planificación. Tu perfil y tus objetivos solo se copian si
            aún no los tienes.
          </Notice>
        )}

        {preview && mapping && (
          <>
            <div className="rounded-lg border border-border bg-surface px-4 py-3">
              <p className="text-[13px] font-medium text-text-3">{FORMAT_LABEL[preview.format]}</p>
              <p className="mt-1 text-[15px] text-text" data-testid="import-summary">
                {fmt(preview.new)} {preview.new === 1 ? 'comida nueva' : 'comidas nuevas'}
                {preview.already > 0 && ` · ${fmt(preview.already)} ya importadas`}
                {preview.duplicates > 0 && ` · ${fmt(preview.duplicates)} parecidas a otras que ya tienes`}
                {preview.error_count > 0 && ` · ${fmt(preview.error_count)} ${preview.error_count === 1 ? 'fila con error' : 'filas con error'}`}
              </p>
            </div>

            {preview.duplicates > 0 && (
              <div className="overflow-hidden rounded-lg border border-border bg-surface">
                <Switch
                  checked={skipDuplicates}
                  onChange={setSkipDuplicates}
                  label="Saltar posibles duplicados"
                  description="Mismo día, momento y calorías que una comida que ya apuntaste."
                />
              </div>
            )}

            <details className="rounded-lg border border-border bg-surface" open={missing.length > 0 || preview.format === 'generico'}>
              <summary className="cursor-pointer px-4 py-3 text-[15px] text-text">Columnas del fichero</summary>
              <div className="grid grid-cols-2 gap-x-3 gap-y-2.5 px-4 pb-4">
                {FIELDS.map((field) => (
                  <label key={field.key} className="flex flex-col gap-1 text-[13px] text-text-2">
                    <span>
                      {field.label}
                      {field.required && <span className="text-danger-text"> *</span>}
                    </span>
                    <select
                      className="min-h-11 w-full min-w-0 truncate rounded-md border border-border bg-surface-2 px-3 text-[14.5px] text-text outline-none focus:border-accent"
                      value={mapping[field.key] ?? ''}
                      onChange={(event) => {
                        const next = { ...mapping, [field.key]: event.target.value || null }
                        setMapping(next)
                        if (file) void loadPreview(file, next, monthFirst)
                      }}
                    >
                      <option value="">— Ninguna —</option>
                      {preview.columns.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <div className="border-t border-border">
                <Switch
                  checked={monthFirst}
                  onChange={(next) => {
                    setMonthFirst(next)
                    if (file) void loadPreview(file, mapping, next)
                  }}
                  label="Fechas en formato mes/día"
                  description="Como 03/25/2026 (exportaciones en inglés de EE. UU.)."
                />
              </div>
            </details>

            {missing.length > 0 && <Notice level="warn">Elige la columna de {missing.map((f) => f.label.toLowerCase()).join(' y ')}.</Notice>}

            {preview.sample.length > 0 && (
              <section aria-label="Primeras comidas que se importarán" className="rounded-lg border border-border bg-surface">
                <p className="px-4 pt-3 text-[13px] font-medium text-text-3">Primeras filas</p>
                <ul>
                  {preview.sample.map((row, index) => (
                    <li key={index} className="flex items-center gap-3 border-b border-border px-4 py-2.5 last:border-b-0">
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[14.5px] text-text">{row.name}</span>
                        <span className="block text-[12.5px] text-text-3">
                          {fmtMedium(row.date)} · {SLOT_BY_KEY[row.slot]?.label ?? row.slot}
                        </span>
                      </span>
                      <span className="shrink-0 text-[14.5px] text-text tabular-nums" data-num>
                        {fmt(row.kcal)} kcal
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {preview.errors.length > 0 && (
              <details className="rounded-lg border border-border bg-surface">
                <summary className="cursor-pointer px-4 py-3 text-[14px] text-text-2">Filas que no se importarán</summary>
                <ul className="space-y-1 px-4 pb-3 text-[13px] text-text-3">
                  {preview.errors.map((item) => (
                    <li key={item.line}>
                      Fila {item.line}: {item.message}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </>
        )}
        {busy && !preview && !isJson && <p className="text-[14px] text-text-3">Leyendo el fichero…</p>}
      </div>
    </Sheet>
  )
}

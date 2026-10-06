import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowRight, Barcode, Camera, Check, ImagePlus, PencilLine, ScanBarcode, Trash2, WifiOff, X } from 'lucide-react'
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useBootstrap, useOnline } from '@/hooks/data'
import { api, ApiError, errorMessage } from '@/lib/api'
import { fmt, fmtSmart } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { downscaleImage } from '@/lib/image'
import { GRAM_MACROS, MACROS } from '@/lib/macros'
import { itemFor } from '@/lib/products'
import type { Bootstrap, LabelDraft, Product } from '@/lib/types'
import { keys } from '@/offline/queryClient'
import { Button } from '@/ui/Button'
import { Field, NumberInput } from '@/ui/Field'
import { Notice } from '@/ui/Notice'
import { Segmented } from '@/ui/Segmented'
import { Sheet } from '@/ui/Sheet'
import { toast } from '@/ui/toast'
import { Analyzing } from './Analyzing'
import { useShell } from './Shell'

// La cámara y el lector de respaldo (zxing-wasm) solo se descargan al escanear.
const BarcodeScanner = lazy(() => import('./BarcodeScanner'))

interface Props {
  open: boolean
  /** Producto a editar; null para guardar uno nuevo desde la foto de su etiqueta. */
  product: Product | null
  onClose: () => void
}

type Phase =
  | { kind: 'pick' }
  | { kind: 'busy'; preview: string }
  | { kind: 'clarify'; question: string }
  | { kind: 'form' }
  | { kind: 'scan' }
  | { kind: 'lookup'; code: string }
  | { kind: 'nocode'; code: string; reason: 'not_found' | 'unavailable' | 'offline' }
type ScanResult = { status: 'ok'; draft: LabelDraft } | { status: 'clarify'; question: string }
type BarcodeResult =
  | { status: 'saved'; product: Product }
  | { status: 'found'; draft: LabelDraft; code: string }
  | { status: 'not_found' | 'unavailable'; code: string }

const NO_CODE: Record<'not_found' | 'unavailable' | 'offline', { title: string; text: string }> = {
  not_found: {
    title: 'Este código no está en Open Food Facts',
    text: 'Haz una foto a la tabla nutricional y la leo yo. El código queda guardado con el producto, así la próxima vez lo reconoceré al escanearlo.',
  },
  unavailable: {
    title: 'Open Food Facts no responde ahora',
    text: 'Puedes volver a intentarlo en un rato o hacer una foto a la tabla nutricional.',
  },
  offline: {
    title: 'Sin conexión',
    text: 'Para buscar un código nuevo necesito red. Los productos que ya guardaste con su código sí se reconocen sin conexión.',
  },
}

interface Fields {
  name: string
  alias: string
  basis: 'g' | 'ml'
  kcal: number | null
  protein: number | null
  carbs: number | null
  fat: number | null
  fiber: number | null
  sugars: number | null
  salt: number | null
  unitLabel: string
  unitGrams: number | null
}

const EMPTY: Fields = {
  name: '',
  alias: '',
  basis: 'g',
  kcal: null,
  protein: null,
  carbs: null,
  fat: null,
  fiber: null,
  sugars: null,
  salt: null,
  unitLabel: '',
  unitGrams: null,
}

const fromProduct = (p: Product): Fields => ({
  name: p.name,
  alias: p.alias,
  basis: p.basis,
  kcal: p.kcal100,
  protein: p.protein100,
  carbs: p.carbs100,
  fat: p.fat100,
  fiber: p.fiber100,
  sugars: p.sugars100,
  salt: p.salt100,
  unitLabel: p.unit_label,
  unitGrams: p.unit_grams,
})

const fromDraft = (d: LabelDraft): Fields => ({
  name: d.name,
  alias: d.alias,
  basis: d.basis,
  kcal: d.kcal100,
  protein: d.protein100,
  carbs: d.carbs100,
  fat: d.fat100,
  fiber: d.fiber100,
  sugars: d.sugars100,
  salt: d.salt100,
  unitLabel: d.unit_label,
  unitGrams: d.unit_grams,
})

function NumberBox({
  label,
  suffix,
  value,
  onChange,
  max,
  accent,
  invalid,
}: {
  label: string
  suffix: string
  value: number | null
  onChange: (value: number | null) => void
  max: number
  accent?: { color: string; text: string; soft: string; letter: string }
  invalid?: boolean
}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center gap-1.5 text-[13px] font-medium text-text-2">
        {accent && (
          <span className="grid size-5 place-items-center rounded-full text-[11px] font-bold" style={{ background: accent.soft, color: accent.text }} aria-hidden>
            {accent.letter}
          </span>
        )}
        {label}
      </span>
      <span
        className={clsx(
          'flex h-13 items-center rounded-md border bg-surface-2 px-3.5 focus-within:border-accent',
          invalid ? 'border-warn' : 'border-border',
        )}
      >
        <NumberInput value={value} onChange={onChange} decimals={2} min={0} max={max} ariaLabel={label} className="h-full min-w-0 flex-1 text-text" />
        <span className="ml-1.5 text-[13.5px] text-text-3">{suffix}</span>
      </span>
    </label>
  )
}

/** Foto de la etiqueta → lectura por la IA → formulario para revisar → producto guardado. */
export function ProductSheet({ open, product, onClose }: Props) {
  const client = useQueryClient()
  const online = useOnline()
  const [phase, setPhase] = useState<Phase>({ kind: 'pick' })
  const [fields, setFields] = useState<Fields>(EMPTY)
  const [warnings, setWarnings] = useState<string[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [barcode, setBarcode] = useState<string | null>(null)
  const { data: bootstrap } = useBootstrap()
  const { openProduct } = useShell()
  const camera = useRef<HTMLInputElement>(null)
  const gallery = useRef<HTMLInputElement>(null)
  const objectUrl = useRef<string | null>(null)
  const editing = !!product

  const set = <K extends keyof Fields>(key: K, value: Fields[K]) => setFields((f) => ({ ...f, [key]: value }))

  function revoke() {
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
    objectUrl.current = null
  }

  useEffect(() => {
    if (!open) return
    revoke()
    setError('')
    setConfirmDelete(false)
    setBlob(null)
    setBarcode(product?.barcode ?? null)
    if (product) {
      setFields(fromProduct(product))
      setWarnings([])
      setImageUrl(product.has_image ? `/api/products/${product.id}/image` : null)
      setPhase({ kind: 'form' })
    } else {
      setFields(EMPTY)
      setWarnings([])
      setImageUrl(null)
      setPhase({ kind: 'pick' })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, product?.id])

  useEffect(() => revoke, [])

  async function onFile(file: File | undefined) {
    if (!file) return
    if (!navigator.onLine) return setError('Necesitas conexión para leer la etiqueta. Puedes rellenarla a mano.')
    setError('')
    try {
      const image = await downscaleImage(file, 1600, 0.85)
      revoke()
      objectUrl.current = URL.createObjectURL(image)
      setBlob(image)
      setImageUrl(objectUrl.current)
      setPhase({ kind: 'busy', preview: objectUrl.current })
      const body = new FormData()
      body.append('image', image, 'etiqueta.jpg')
      const result = await api.post<ScanResult>('/api/products/scan', body)
      if (result.status === 'clarify') return setPhase({ kind: 'clarify', question: result.question })
      setFields(fromDraft(result.draft))
      setWarnings(result.draft.warnings)
      haptic('success')
      setPhase({ kind: 'form' })
    } catch (err) {
      setError(err instanceof ApiError && err.offline ? 'Se ha cortado la conexión. Inténtalo de nuevo o rellénala a mano.' : errorMessage(err))
      haptic('error')
      setPhase({ kind: 'pick' })
    }
  }

  /** Código leído o escrito: primero lo que ya está guardado (también sin red), luego Open Food Facts. */
  async function lookupCode(code: string) {
    setError('')
    const saved = bootstrap?.products.find((p) => p.barcode === code)
    if (saved) {
      toast.success('Ya lo tienes guardado', saved.alias || saved.name)
      return openProduct(saved)
    }
    setBarcode(code)
    if (!navigator.onLine) return setPhase({ kind: 'nocode', code, reason: 'offline' })
    setPhase({ kind: 'lookup', code })
    try {
      const result = await api.get<BarcodeResult>(`/api/products/barcode/${code}`)
      if (result.status === 'saved') {
        toast.success('Ya lo tienes guardado', result.product.alias || result.product.name)
        return openProduct(result.product)
      }
      if (result.status === 'found') {
        setFields(fromDraft(result.draft))
        setWarnings(result.draft.warnings)
        setImageUrl(null)
        haptic('success')
        return setPhase({ kind: 'form' })
      }
      setPhase({ kind: 'nocode', code, reason: result.status })
    } catch (err) {
      if (err instanceof ApiError && err.offline) return setPhase({ kind: 'nocode', code, reason: 'offline' })
      setError(errorMessage(err))
      setPhase({ kind: 'pick' })
    }
  }

  const macrosSum = (fields.protein ?? 0) + (fields.carbs ?? 0) + (fields.fat ?? 0)
  const missing = [fields.kcal, fields.protein, fields.carbs, fields.fat].some((v) => v === null)
  const tooMuch = macrosSum > 105
  const valid = fields.name.trim().length > 0 && !missing && !tooMuch && (fields.kcal ?? 0) <= 950

  // Vista previa viva: lo que saldrá cuando escribas «2 …» con estas cifras.
  const preview = useMemo(() => {
    if (missing || tooMuch) return null
    const info = {
      id: product?.id ?? 0,
      name: fields.name.trim() || 'Producto',
      alias: fields.alias,
      basis: fields.basis,
      kcal100: fields.kcal ?? 0,
      protein100: fields.protein ?? 0,
      carbs100: fields.carbs ?? 0,
      fat100: fields.fat ?? 0,
      unit_label: fields.unitLabel,
      unit_grams: fields.unitGrams,
    }
    return fields.unitGrams ? { two: itemFor(info, 2, null), one: itemFor(info, 1, null) } : { hundred: itemFor(info, 100, 'g') }
  }, [fields, missing, tooMuch, product?.id])

  const payload = () => ({
    name: fields.name.trim(),
    alias: fields.alias.trim(),
    basis: fields.basis,
    kcal100: fields.kcal,
    protein100: fields.protein,
    carbs100: fields.carbs,
    fat100: fields.fat,
    fiber100: fields.fiber,
    sugars100: fields.sugars,
    salt100: fields.salt,
    unit_label: fields.unitLabel.trim(),
    unit_grams: fields.unitGrams,
    barcode,
  })

  const putInCache = (saved: Product) =>
    client.setQueryData<Bootstrap>(keys.bootstrap, (old) => {
      if (!old) return old
      const others = old.products.filter((p) => p.id !== saved.id)
      return { ...old, products: [saved, ...others] }
    })

  async function save() {
    if (!valid || busy) return
    if (!navigator.onLine) return setError('Necesitas conexión para guardar el producto.')
    setBusy(true)
    setError('')
    try {
      let saved: Product
      if (product) {
        saved = await api.patch<Product>(`/api/products/${product.id}`, payload())
      } else {
        const body = new FormData()
        body.append('data', JSON.stringify(payload()))
        if (blob) body.append('image', blob, 'etiqueta.jpg')
        saved = await api.post<Product>('/api/products', body)
      }
      putInCache(saved)
      haptic('success')
      toast.success(product ? 'Producto actualizado' : `Guardado: ${saved.alias || saved.name}`, product ? undefined : `Ahora puedes escribir «2 ${saved.alias}» y sumo sus calorías.`)
      onClose()
    } catch (err) {
      setError(errorMessage(err))
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!product || busy) return
    setBusy(true)
    try {
      await api.delete(`/api/products/${product.id}`)
      client.setQueryData<Bootstrap>(keys.bootstrap, (old) => (old ? { ...old, products: old.products.filter((p) => p.id !== product.id) } : old))
      haptic('warning')
      toast({ title: 'Producto borrado', description: product.name })
      onClose()
    } catch (err) {
      setError(errorMessage(err))
      setConfirmDelete(false)
    } finally {
      setBusy(false)
    }
  }

  const title = editing
    ? 'Editar producto'
    : phase.kind === 'form'
      ? barcode && !blob
        ? 'Revisa el producto'
        : 'Revisa la etiqueta'
      : phase.kind === 'scan'
        ? 'Escanea el código'
        : 'Guardar un producto'
  const footer =
    phase.kind === 'form' ? (
      <div className="space-y-2">
        <Button size="lg" block onClick={save} loading={busy && !confirmDelete} disabled={!valid || !online} icon={<Check className="size-5" aria-hidden />}>
          {editing ? 'Guardar cambios' : 'Guardar producto'}
        </Button>
      </div>
    ) : null

  return (
    <Sheet open={open} onClose={onClose} title={title} footer={footer} tall={phase.kind === 'form'}>
      <input ref={camera} type="file" accept="image/*" capture="environment" className="hidden" tabIndex={-1} aria-hidden onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = '' }} />
      <input ref={gallery} type="file" accept="image/*" className="hidden" tabIndex={-1} aria-hidden onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = '' }} />

      {phase.kind === 'pick' && (
        <div className="space-y-3 pt-1">
          <p className="text-[15px] leading-relaxed text-text-2">
            Haz una foto a la tabla de <strong className="font-semibold text-text">información nutricional</strong> (la parte de atrás del envase). La leo, la revisas y la guardo: cuando escribas «dos yogures» usaré esas cifras exactas.
          </p>
          {!online && (
            <Notice level="info">
              <span className="flex items-center gap-2">
                <WifiOff className="size-4 shrink-0" aria-hidden /> Sin conexión no puedo leer la foto.
              </span>
            </Notice>
          )}
          {error && <Notice level="warn">{error}</Notice>}
          <Button size="lg" block onClick={() => setPhase({ kind: 'scan' })} icon={<ScanBarcode className="size-5" aria-hidden />}>
            Escanear el código de barras
          </Button>
          <Button size="lg" block variant="secondary" disabled={!online} onClick={() => camera.current?.click()} icon={<Camera className="size-5" aria-hidden />}>
            Hacer foto a la etiqueta
          </Button>
          <Button size="lg" block variant="secondary" disabled={!online} onClick={() => gallery.current?.click()} icon={<ImagePlus className="size-5" aria-hidden />}>
            Elegir una foto
          </Button>
          <Button size="md" block variant="ghost" onClick={() => setPhase({ kind: 'form' })} icon={<PencilLine className="size-[18px]" aria-hidden />}>
            Prefiero rellenarlo a mano
          </Button>
          <ul className="space-y-1.5 rounded-md bg-surface-2 p-3.5 text-[13.5px] leading-snug text-text-2">
            <li>· Busca la tabla con las calorías «por 100 g» o «por 100 ml».</li>
            <li>· Con buena luz y sin reflejos, para que se lean bien las cifras.</li>
            <li>· Si la etiqueta es larga, enfoca solo la tabla.</li>
          </ul>
        </div>
      )}

      {phase.kind === 'busy' && <Analyzing mode="label" preview={phase.preview} />}

      {phase.kind === 'scan' && (
        <Suspense fallback={<div className="skeleton aspect-[4/3] !rounded-[22px]" role="status" aria-label="Preparando la cámara" />}>
          <BarcodeScanner onDetected={(code) => void lookupCode(code)} onCancel={() => setPhase({ kind: 'pick' })} />
        </Suspense>
      )}

      {phase.kind === 'lookup' && (
        <div className="py-10 text-center" role="status">
          <Barcode className="mx-auto size-9 animate-pulse-soft text-accent-text" aria-hidden />
          <p className="mt-3 text-[15px] text-text-2">Buscando el código {phase.code}…</p>
        </div>
      )}

      {phase.kind === 'nocode' && (
        <div className="space-y-3 pt-1">
          <Notice level={phase.reason === 'not_found' ? 'info' : 'warn'}>
            <strong className="block font-semibold">{NO_CODE[phase.reason].title}</strong>
            {NO_CODE[phase.reason].text}
          </Notice>
          <p className="text-[13px] text-text-3" data-num>
            Código {phase.code}
          </p>
          <Button size="lg" block disabled={!online} onClick={() => camera.current?.click()} icon={<Camera className="size-5" aria-hidden />}>
            Hacer foto a la etiqueta
          </Button>
          {phase.reason !== 'not_found' && (
            <Button size="lg" block variant="secondary" disabled={!online} onClick={() => void lookupCode(phase.code)}>
              Volver a buscar
            </Button>
          )}
          <Button block variant="ghost" onClick={() => setPhase({ kind: 'form' })} icon={<PencilLine className="size-[18px]" aria-hidden />}>
            Rellenarlo a mano
          </Button>
        </div>
      )}

      {phase.kind === 'clarify' && (
        <div className="space-y-4 pt-1">
          {imageUrl && <img src={imageUrl} alt="La foto que has hecho" className="mx-auto max-h-56 rounded-md border border-border object-contain" />}
          <Notice level="warn">{phase.question}</Notice>
          <Button block size="lg" onClick={() => camera.current?.click()} icon={<Camera className="size-5" aria-hidden />}>
            Hacer otra foto
          </Button>
          <Button block variant="ghost" onClick={() => setPhase({ kind: 'form' })}>
            Rellenarlo a mano
          </Button>
        </div>
      )}

      {phase.kind === 'form' && (
        <div className="space-y-5 pt-1">
          {imageUrl && (
            <a href={imageUrl} target="_blank" rel="noreferrer" aria-label="Ver la foto de la etiqueta a tamaño completo" className="block">
              <img src={imageUrl} alt="Foto de la etiqueta" className="mx-auto max-h-48 rounded-md border border-border object-contain" />
            </a>
          )}
          {!editing && imageUrl && <p className="text-center text-[12.5px] text-text-3">Compara las cifras con la foto antes de guardar.</p>}
          {warnings.length > 0 && (
            <div className="space-y-2">
              {warnings.map((w) => (
                <Notice key={w} level="warn">
                  {w}
                </Notice>
              ))}
            </div>
          )}
          {error && <Notice level="danger">{error}</Notice>}
          {!online && <Notice level="info">Sin conexión: puedes revisar el producto, pero guardar necesita red.</Notice>}

          {barcode && (
            <p className="flex items-center gap-2 text-[13px] text-text-3">
              <Barcode className="size-4 shrink-0" aria-hidden />
              <span data-num>Código de barras {barcode}</span>
              <button type="button" onClick={() => setBarcode(null)} aria-label="Quitar el código de barras" className="-my-2 grid size-11 place-items-center rounded-full hover:text-text">
                <X className="size-4" aria-hidden />
              </button>
            </p>
          )}
          <Field label="Nombre del producto" value={fields.name} onChange={(e) => set('name', e.target.value)} maxLength={120} autoComplete="off" enterKeyHint="next" />
          <Field
            label="Cómo lo escribirás al apuntar"
            hint="Por ejemplo «yogur ligero»: así lo reconoceré en «dos yogures ligeros»."
            value={fields.alias}
            onChange={(e) => set('alias', e.target.value)}
            maxLength={60}
            autoComplete="off"
            autoCapitalize="none"
            enterKeyHint="next"
          />

          <div>
            <span className="eyebrow">Valores de la etiqueta</span>
            <Segmented
              className="mt-2"
              label="Referencia de la tabla"
              value={fields.basis}
              onChange={(v) => set('basis', v)}
              options={[
                { value: 'g', label: 'Por 100 g' },
                { value: 'ml', label: 'Por 100 ml' },
              ]}
            />
            <div className="mt-3 grid grid-cols-2 gap-3">
              <NumberBox label="Calorías" suffix="kcal" value={fields.kcal} onChange={(v) => set('kcal', v)} max={950} accent={{ ...MACROS.kcal, letter: 'K' }} invalid={fields.kcal === null} />
              {GRAM_MACROS.map((m) => {
                const key = m.key === 'protein' ? 'protein' : m.key === 'carbs' ? 'carbs' : 'fat'
                return <NumberBox key={m.key} label={m.label} suffix="g" value={fields[key]} onChange={(v) => set(key, v)} max={100} accent={m} invalid={fields[key] === null || tooMuch} />
              })}
            </div>
            {tooMuch && <p className="mt-2 text-[13px] text-warn-text">Proteínas, hidratos y grasas no pueden sumar más de 100 g por cada 100 g.</p>}
            {missing && !tooMuch && <p className="mt-2 text-[13px] text-text-3">Completa los cuatro valores para poder guardar.</p>}
          </div>

          <div>
            <span className="eyebrow">Una unidad</span>
            <p className="mt-1 text-[13px] leading-snug text-text-3">Lo que pesa uno (un yogur, una galleta…). Con esto, «dos» se multiplica solo.</p>
            <div className="mt-2 grid grid-cols-[1fr_1fr] gap-3">
              <Field label="Se llama" value={fields.unitLabel} onChange={(e) => set('unitLabel', e.target.value)} placeholder="yogur" maxLength={30} autoComplete="off" autoCapitalize="none" enterKeyHint="next" />
              <NumberBox label={fields.basis === 'ml' ? 'Pesa (ml)' : 'Pesa (g)'} suffix={fields.basis} value={fields.unitGrams} onChange={(v) => set('unitGrams', v && v > 0 ? v : null)} max={5000} />
            </div>
          </div>

          <details className="rounded-md border border-border bg-surface px-3.5 py-1">
            <summary className="flex min-h-11 cursor-pointer items-center text-[14px] font-medium text-text-2">Más datos de la etiqueta (opcional)</summary>
            <div className="grid grid-cols-3 gap-2.5 pt-1 pb-3">
              <NumberBox label="Fibra" suffix="g" value={fields.fiber} onChange={(v) => set('fiber', v)} max={100} />
              <NumberBox label="Azúcares" suffix="g" value={fields.sugars} onChange={(v) => set('sugars', v)} max={100} />
              <NumberBox label="Sal" suffix="g" value={fields.salt} onChange={(v) => set('salt', v)} max={100} />
            </div>
          </details>

          {preview && (
            <div className="rounded-lg bg-accent-soft p-4" aria-live="polite">
              <p className="flex items-center gap-1.5 text-[12.5px] font-semibold text-accent-text">
                <ArrowRight className="size-3.5" aria-hidden /> Así lo contaré
              </p>
              {'two' in preview && preview.two && preview.one ? (
                <p className="mt-1.5 text-[15px] leading-snug text-text">
                  «2 {fields.alias.trim() || fields.unitLabel || 'unidades'}» ={' '}
                  <strong className="font-semibold" data-num>
                    {fmtSmart(preview.two.grams)} {fields.basis} · {fmt(preview.two.kcal)} kcal
                  </strong>
                  <span className="mt-0.5 block text-[13px] text-text-2" data-num>
                    Cada unidad: {fmt(preview.one.kcal)} kcal · P {fmtSmart(preview.one.protein)} · H {fmtSmart(preview.one.carbs)} · G {fmtSmart(preview.one.fat)}
                  </span>
                </p>
              ) : (
                'hundred' in preview &&
                preview.hundred && (
                  <p className="mt-1.5 text-[15px] leading-snug text-text">
                    «100 {fields.basis} de {fields.alias.trim() || 'este producto'}» ={' '}
                    <strong className="font-semibold" data-num>
                      {fmt(preview.hundred.kcal)} kcal
                    </strong>
                    <span className="mt-0.5 block text-[13px] text-text-2">Añade lo que pesa una unidad para poder escribir «dos» o «un».</span>
                  </p>
                )
              )}
            </div>
          )}

          {editing && (
            <div className="pt-1">
              {confirmDelete ? (
                <div className="rounded-md bg-danger-soft p-3.5">
                  <p className="text-[14px] leading-snug text-text">Se borrará el producto y la foto de su etiqueta. Las comidas ya apuntadas no cambian.</p>
                  <div className="mt-3 flex gap-2">
                    <Button variant="danger" size="sm" loading={busy} onClick={() => void remove()} icon={<Trash2 className="size-4" aria-hidden />}>
                      Sí, borrar
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>
                      Cancelar
                    </Button>
                  </div>
                </div>
              ) : (
                <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)} icon={<Trash2 className="size-4" aria-hidden />}>
                  Borrar producto
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </Sheet>
  )
}

export default ProductSheet

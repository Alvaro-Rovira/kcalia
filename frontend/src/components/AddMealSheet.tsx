import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AnimatePresence, motion } from 'motion/react'
import {
  ArrowUp,
  Camera,
  Check,
  History,
  Info,
  Mic,
  RotateCcw,
  Sparkles,
  Square,
  Star,
  Tag,
  WifiOff,
  X,
  Zap,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useBootstrap, useMealActions, useOnline } from '@/hooks/data'
import { useRecorder, type RecorderError } from '@/hooks/useRecorder'
import { api, ApiError, errorMessage } from '@/lib/api'
import { relativeDay, todayISO } from '@/lib/dates'
import { capitalize, fmt } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { downscaleImage } from '@/lib/image'
import { drinkItem, type Drink } from '@/lib/drinks'
import { itemsTotal } from '@/lib/macros'
import { draftFromProducts, resolveText, singleItem } from '@/lib/products'
import { rankForSlot } from '@/lib/ranking'
import { draftFromDish, matchLocally, suggestDishes } from '@/lib/resolve'
import { slotForTime } from '@/lib/slots'
import type { Dish, Draft, Item, Meal, Product, ResolveResult, Slot, Source, Via } from '@/lib/types'
import { keys } from '@/offline/queryClient'
import { Button } from '@/ui/Button'
import { MacroBar, MacroInline } from '@/ui/MacroBar'
import { Notice } from '@/ui/Notice'
import { Sheet } from '@/ui/Sheet'
import { toast } from '@/ui/toast'
import { Analyzing } from './Analyzing'
import { DrinkPicker } from './DrinkPicker'
import { ItemList, ServingsPicker, SlotPicker, Totals } from './MealBreakdown'

interface Props {
  open: boolean
  date: string
  slot?: Slot
  onClose: () => void
  onSaved: (date: string) => void
  /** Abre la hoja para guardar la etiqueta de un producto nuevo. */
  onNewProduct: () => void
}

type Phase =
  | { kind: 'input' }
  | { kind: 'busy'; mode: 'text' | 'photo' | 'voice'; preview?: string }
  | { kind: 'fuzzy'; candidates: Draft[] }
  | { kind: 'result'; draft: Draft; via: Via }
  | { kind: 'clarify'; question: string }
  | { kind: 'offline' }

const RECORDER_ERRORS: Record<RecorderError, [string, string]> = {
  denied: ['No tengo permiso para usar el micrófono', 'Actívalo en los ajustes del navegador para este sitio.'],
  unsupported: ['Este navegador no permite grabar audio', 'Puedes escribir la comida o usar una foto.'],
  failed: ['No se ha podido grabar', 'Inténtalo otra vez o escribe la comida.'],
}

const SOURCE_BADGE: Partial<Record<Source, { label: string; Icon: typeof Zap; saved: boolean }>> = {
  ai: { label: 'Analizado con IA', Icon: Sparkles, saved: false },
  photo: { label: 'Estimado desde tu foto', Icon: Camera, saved: false },
  cache: { label: 'Sin IA · ingredientes conocidos', Icon: Zap, saved: true },
  exact: { label: 'Sin IA · de tu historial', Icon: History, saved: true },
  fuzzy: { label: 'Sin IA · de tu historial', Icon: History, saved: true },
  product: { label: 'Sin IA · con tu etiqueta', Icon: Tag, saved: true },
}

function confidenceLabel(value: number): { text: string; level: number } {
  if (value >= 0.8) return { text: 'Confianza alta', level: 3 }
  if (value >= 0.55) return { text: 'Confianza media', level: 2 }
  return { text: 'Confianza baja: revisa las cantidades', level: 1 }
}

function RecordingPanel({ seconds, level, max, onStop, onCancel }: { seconds: number; level: number; max: number; onStop: () => void; onCancel: () => void }) {
  const bars = 21
  return (
    <div className="flex flex-col items-center py-6">
      <p className="text-[15px] font-medium text-text" role="status">
        Te escucho. Cuéntame qué has comido.
      </p>
      <div className="mt-6 flex h-16 items-center gap-[5px]" aria-hidden>
        {Array.from({ length: bars }, (_, i) => {
          const centre = 1 - Math.abs(i - (bars - 1) / 2) / ((bars - 1) / 2)
          const height = 6 + (0.25 + centre * 0.75) * level * 58 * (0.7 + ((i * 37) % 10) / 33)
          return <span key={i} className="w-1 rounded-full bg-accent transition-[height] duration-100" style={{ height: Math.min(64, height) }} />
        })}
      </div>
      <p className="mt-4 text-[14px] text-text-3" data-num aria-label={`${seconds} segundos grabados`}>
        0:{String(seconds).padStart(2, '0')} / {Math.floor(max / 60)}:{String(max % 60).padStart(2, '0')}
      </p>
      <div className="mt-6 flex w-full gap-3">
        <Button variant="secondary" onClick={onCancel} className="flex-1">
          Cancelar
        </Button>
        <Button onClick={onStop} className="flex-[2]" icon={<Square className="size-4 fill-current" aria-hidden />}>
          Listo
        </Button>
      </div>
    </div>
  )
}

function QuickChip({ dish, onPick }: { dish: Dish; onPick: (dish: Dish) => void }) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.95 }}
      onClick={() => onPick(dish)}
      aria-label={`Añadir ${dish.name}, ${fmt(dish.kcal)} kilocalorías`}
      className="flex h-11 max-w-[220px] shrink-0 items-center gap-2 rounded-full border border-border bg-surface-2 pr-3.5 pl-3 text-[14px] font-medium text-text"
    >
      {dish.favorite && <Star className="size-3.5 shrink-0 fill-carbs text-carbs" aria-hidden />}
      <span className="truncate">{dish.name}</span>
      <span className="shrink-0 text-[12.5px] text-text-3" data-num>
        {fmt(dish.kcal)}
      </span>
    </motion.button>
  )
}

export default function AddMealSheet({ open, date: initialDate, slot: initialSlot, onClose, onSaved, onNewProduct }: Props) {
  const client = useQueryClient()
  const { data: bootstrap } = useBootstrap()
  const online = useOnline()
  const meals = useMealActions()
  const dishes = useMemo(() => bootstrap?.dishes ?? [], [bootstrap?.dishes])
  const products = useMemo(() => bootstrap?.products ?? [], [bootstrap?.products])

  const [phase, setPhase] = useState<Phase>({ kind: 'input' })
  const [text, setText] = useState('')
  const [date, setDate] = useState(initialDate)
  const [slot, setSlot] = useState<Slot>(initialSlot ?? slotForTime())
  const [notice, setNotice] = useState('')
  const [servings, setServings] = useState(1)
  const [saved, setSaved] = useState(false)
  const via = useRef<Via>('text')
  const abort = useRef<AbortController | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const previewUrl = useRef<string | null>(null)

  useEffect(() => {
    if (!open) {
      abort.current?.abort()
      return
    }
    setPhase({ kind: 'input' })
    setText('')
    setNotice('')
    setServings(1)
    setSaved(false)
    setDate(initialDate)
    setSlot(initialSlot ?? (initialDate === todayISO() ? slotForTime() : 'comida'))
    via.current = 'text'
  }, [open, initialDate, initialSlot])

  useEffect(
    () => () => {
      if (previewUrl.current) URL.revokeObjectURL(previewUrl.current)
    },
    [],
  )

  // Ordenados para el momento elegido (al abrir, el de la hora): el café arriba por la mañana, la cena por la noche.
  const favorites = useMemo(() => rankForSlot(dishes.filter((d) => d.favorite), slot), [dishes, slot])
  const recents = useMemo(() => rankForSlot(dishes.filter((d) => !d.favorite).slice(0, 30), slot).slice(0, 12), [dishes, slot])
  const rankedProducts = useMemo(() => rankForSlot(products, slot), [products, slot])
  const suggestions = useMemo(() => suggestDishes(text, dishes), [text, dishes])

  /** Guarda y cierra. El aviso permite deshacer sin pedir confirmaciones. */
  const save = useCallback(
    (draft: Draft, options: { source: Source; servings?: number; name?: string; items?: Item[]; via?: Via }) => {
      const items = options.items ?? draft.items
      const portion = options.servings ?? 1
      const meal: Meal = meals.add({
        date,
        slot,
        name: (options.name ?? draft.name).trim() || 'Comida',
        text: draft.text,
        items,
        servings: portion,
        source: options.source,
        via: options.via ?? via.current,
        confidence: draft.confidence,
        assumptions: draft.assumptions,
        dish_id: draft.dish_id,
      })
      haptic('success')
      const total = itemsTotal(items, portion)
      const withoutAi = options.source !== 'ai' && options.source !== 'photo'
      toast({
        tone: 'success',
        title: `${meal.name} · ${fmt(total.kcal)} kcal`,
        description: options.source === 'drink' ? 'Sin gastar IA' : options.source === 'product' ? 'Con la etiqueta de tu producto, sin gastar IA' : withoutAi ? 'Añadida desde tu historial, sin gastar IA' : `Añadida a ${relativeDay(date).toLowerCase()}`,
        action: { label: 'Deshacer', onClick: () => meals.remove(meal) },
      })
      onSaved(date)
      onClose()
    },
    [date, slot, meals, onClose, onSaved],
  )

  const analyze = useCallback(
    async (input: string, options: { skipHistory?: boolean; forceAi?: boolean } = {}) => {
      const query = input.trim()
      if (!query) {
        textarea.current?.focus()
        return
      }
      setNotice('')
      if (!options.skipHistory && !options.forceAi) {
        // Primero lo que ya hay en el móvil: instantáneo y funciona sin red.
        const local = matchLocally(query, dishes)
        if (local?.status === 'exact') return save(local.draft, { source: 'exact' })
        if (local?.status === 'fuzzy') return setPhase({ kind: 'fuzzy', candidates: local.candidates })
      }
      if (!options.forceAi && products.length) {
        // Productos con etiqueta guardada: «dos yogures ligeros» sale de sus cifras, al instante y sin red.
        const found = resolveText(query, products)
        if (found.items.length && !found.rest.length) {
          setServings(1)
          setPhase({ kind: 'result', draft: draftFromProducts(query, found.items), via: via.current })
          haptic('success')
          return
        }
      }
      if (!navigator.onLine) return setPhase({ kind: 'offline' })

      setPhase({ kind: 'busy', mode: 'text' })
      abort.current = new AbortController()
      try {
        const result = await api.post<ResolveResult>(
          '/api/meals/resolve',
          { text: query, skip_history: !!options.skipHistory, force_ai: !!options.forceAi },
          abort.current.signal,
        )
        if (result.status === 'exact') return save(result.draft, { source: 'exact' })
        if (result.status === 'fuzzy') return setPhase({ kind: 'fuzzy', candidates: result.candidates })
        if (result.status === 'clarify') return setPhase({ kind: 'clarify', question: result.question })
        setServings(1)
        setPhase({ kind: 'result', draft: result.draft, via: via.current })
        haptic('success')
        if (result.status === 'ai') void client.invalidateQueries({ queryKey: keys.stats })
      } catch (error) {
        if (error instanceof DOMException) return
        if (error instanceof ApiError && error.offline) return setPhase({ kind: 'offline' })
        setNotice(errorMessage(error))
        setPhase({ kind: 'input' })
        haptic('error')
      }
    },
    [dishes, products, save, client],
  )

  const recorder = useRecorder(
    async ({ blob, filename }) => {
      setPhase({ kind: 'busy', mode: 'voice' })
      const form = new FormData()
      form.append('audio', blob, filename)
      try {
        const { text: heard } = await api.post<{ text: string }>('/api/transcribe', form)
        via.current = 'voice'
        setText(heard)
        await analyze(heard)
      } catch (error) {
        setNotice(errorMessage(error))
        setPhase({ kind: 'input' })
      }
    },
    (error) => {
      const [title, description] = RECORDER_ERRORS[error]
      toast.error(title, description)
    },
  )

  async function onPhoto(file: File | undefined) {
    if (!file) return
    if (!navigator.onLine) return setPhase({ kind: 'offline' })
    setNotice('')
    try {
      const image = await downscaleImage(file)
      if (previewUrl.current) URL.revokeObjectURL(previewUrl.current)
      previewUrl.current = URL.createObjectURL(image)
      setPhase({ kind: 'busy', mode: 'photo', preview: previewUrl.current })
      const form = new FormData()
      form.append('image', image, 'comida.jpg')
      form.append('note', text.trim())
      abort.current = new AbortController()
      const result = await api.post<ResolveResult>('/api/meals/photo', form, abort.current.signal)
      if (result.status === 'clarify') return setPhase({ kind: 'clarify', question: result.question })
      if (result.status !== 'ai') return setPhase({ kind: 'input' })
      via.current = 'photo'
      setServings(1)
      setPhase({ kind: 'result', draft: result.draft, via: 'photo' })
      haptic('success')
      void client.invalidateQueries({ queryKey: keys.stats })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      setNotice(error instanceof ApiError ? error.message : 'No he podido leer esa imagen. Prueba con otra foto.')
      setPhase({ kind: 'input' })
    }
  }

  const quickProduct = (product: Product) => {
    setServings(1)
    setPhase({ kind: 'result', draft: draftFromProducts(product.alias || product.name, [singleItem(product)]), via: 'tap' })
    haptic('select')
  }

  const quickDrink = (drink: Drink) => {
    const item = drinkItem(drink)
    const draft: Draft = {
      name: drink.name,
      text: '',
      items: [item],
      ...itemsTotal([item]),
      confidence: 1,
      assumptions: ['El alcohol cuenta 7 kcal por gramo'],
      source: 'drink',
      dish_id: null,
    }
    save(draft, { source: 'drink', via: 'tap' })
  }

  const quickAdd = (dish: Dish) => save(draftFromDish(dish, dish.favorite ? 'favorite' : 'recent'), { source: dish.favorite ? 'favorite' : 'recent', via: 'tap' })

  const title =
    phase.kind === 'result' ? 'Revisa y guarda' : phase.kind === 'fuzzy' ? '¿Es esta comida?' : phase.kind === 'clarify' ? 'Necesito un detalle más' : 'Añadir comida'

  let footer = null
  if (phase.kind === 'result') {
    const total = itemsTotal(phase.draft.items, servings)
    footer = (
      <Button
        size="lg"
        block
        disabled={saved}
        onClick={() => {
          setSaved(true)
          const { draft } = phase
          setTimeout(() => save(draft, { source: draft.source, servings, name: draft.name, items: draft.items, via: phase.via }), 380)
        }}
        className={clsx(saved && '!opacity-100')}
      >
        <AnimatePresence mode="wait" initial={false}>
          {saved ? (
            <motion.span key="ok" initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 22 }} className="flex items-center gap-2">
              <Check className="size-5" strokeWidth={3} aria-hidden /> Guardado
            </motion.span>
          ) : (
            <motion.span key="save" exit={{ opacity: 0, scale: 0.9 }} className="flex items-center gap-2" data-num>
              Guardar · {fmt(total.kcal)} kcal
            </motion.span>
          )}
        </AnimatePresence>
      </Button>
    )
  }

  return (
    <Sheet open={open} onClose={onClose} title={title} footer={footer}>
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        className="hidden"
        aria-hidden
        tabIndex={-1}
        onChange={(event) => {
          void onPhoto(event.target.files?.[0])
          event.target.value = ''
        }}
      />

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={recorder.recording ? 'recording' : phase.kind}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, transition: { duration: 0.1 } }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        >
          {recorder.recording ? (
            <RecordingPanel seconds={recorder.seconds} level={recorder.level} max={recorder.maxSeconds} onStop={() => recorder.stop()} onCancel={() => recorder.stop(true)} />
          ) : phase.kind === 'input' ? (
            <div>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  via.current = via.current === 'voice' ? 'voice' : 'text'
                  void analyze(text)
                }}
              >
                <div className="rounded-lg border border-border bg-surface-2 transition-colors focus-within:border-accent">
                  <label htmlFor="meal-text" className="sr-only">
                    Describe lo que has comido
                  </label>
                  <textarea
                    id="meal-text"
                    ref={textarea}
                    value={text}
                    onChange={(event) => {
                      via.current = 'text'
                      setText(event.target.value)
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault()
                        void analyze(text)
                      }
                    }}
                    autoFocus
                    rows={3}
                    maxLength={600}
                    enterKeyHint="send"
                    placeholder="¿Qué has comido? Por ejemplo: dos huevos revueltos con una tostada de pan integral y aceite"
                    className="block w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-[17px] leading-snug text-text outline-none placeholder:text-text-3"
                  />
                  <div className="flex items-center gap-1 px-2 pb-2">
                    <button
                      type="button"
                      onClick={() => void recorder.start()}
                      aria-label="Dictar la comida"
                      className="grid size-11 place-items-center rounded-full text-text-2 transition-colors hover:bg-surface-3 hover:text-text"
                    >
                      <Mic className="size-[21px]" aria-hidden />
                    </button>
                    <button
                      type="button"
                      onClick={() => fileInput.current?.click()}
                      aria-label="Hacer o elegir una foto de la comida"
                      className="grid size-11 place-items-center rounded-full text-text-2 transition-colors hover:bg-surface-3 hover:text-text"
                    >
                      <Camera className="size-[21px]" aria-hidden />
                    </button>
                    <span className="flex-1" />
                    <motion.button
                      type="submit"
                      whileTap={{ scale: 0.9 }}
                      disabled={!text.trim()}
                      aria-label="Analizar comida"
                      className="grid size-11 place-items-center rounded-full bg-accent text-on-accent transition-opacity disabled:opacity-30"
                    >
                      <ArrowUp className="size-5" strokeWidth={2.6} aria-hidden />
                    </motion.button>
                  </div>
                </div>
              </form>

              {notice && (
                <Notice level="warn" className="mt-3">
                  {notice}
                </Notice>
              )}
              {!online && (
                <Notice level="info" className="mt-3">
                  Estás sin conexión. Las comidas de tu historial se pueden añadir igual y se sincronizan al volver la red.
                </Notice>
              )}
              {bootstrap && !bootstrap.ai.configured && online && (
                <Notice level="info" className="mt-3">
                  La IA aún no está configurada en el servidor. De momento solo se pueden añadir comidas de tu historial.
                </Notice>
              )}

              {suggestions.length > 0 && (
                <div className="mt-4">
                  <p className="eyebrow">De tu historial · sin IA</p>
                  <ul className="mt-2 overflow-hidden rounded-md border border-border bg-surface">
                    {suggestions.map((dish) => (
                      <li key={dish.id} className="border-b border-border last:border-b-0">
                        <button type="button" onClick={() => quickAdd(dish)} className="flex min-h-[52px] w-full items-center gap-3 px-3.5 py-2 text-left active:bg-surface-2">
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-[14.5px] font-medium text-text">{dish.name}</p>
                            <MacroInline macros={dish} />
                          </div>
                          <span className="shrink-0 text-[14px] font-semibold text-text" data-num>
                            {fmt(dish.kcal)} <span className="text-[12px] font-medium text-text-3">kcal</span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-5">
                <SlotPicker value={slot} onChange={setSlot} />
                <label className="mt-3 flex min-h-11 items-center justify-between gap-3 text-[14px] text-text-2">
                  <span>
                    Se añadirá a <strong className="font-semibold text-text">{relativeDay(date).toLowerCase()}</strong>
                  </span>
                  <input
                    type="date"
                    value={date}
                    max={todayISO()}
                    onChange={(event) => event.target.value && setDate(event.target.value)}
                    aria-label="Cambiar el día"
                    className="h-11 rounded-sm border border-border bg-surface-2 px-2.5 text-[14px] text-text"
                  />
                </label>
              </div>

              {favorites.length > 0 && (
                <div className="mt-5">
                  <p className="eyebrow">Favoritos</p>
                  <div className="no-scrollbar -mx-5 mt-2 flex gap-2 overflow-x-auto px-5">
                    {favorites.map((dish) => (
                      <QuickChip key={dish.id} dish={dish} onPick={quickAdd} />
                    ))}
                  </div>
                </div>
              )}
              {products.length > 0 && (
                <div className="mt-5">
                  <p className="eyebrow">Mis productos</p>
                  <div className="no-scrollbar -mx-5 mt-2 flex gap-2 overflow-x-auto px-5">
                    {rankedProducts.slice(0, 12).map((product) => (
                      <motion.button
                        key={product.id}
                        type="button"
                        whileTap={{ scale: 0.95 }}
                        onClick={() => quickProduct(product)}
                        aria-label={`Añadir ${product.alias || product.name}`}
                        className="flex h-11 max-w-[220px] shrink-0 items-center gap-2 rounded-full border border-border bg-surface-2 pr-3.5 pl-3 text-[14px] font-medium text-text"
                      >
                        <Tag className="size-3.5 shrink-0 text-accent-text" aria-hidden />
                        <span className="truncate">{product.alias || product.name}</span>
                      </motion.button>
                    ))}
                  </div>
                </div>
              )}
              <DrinkPicker onPick={quickDrink} />
              <button
                type="button"
                onClick={onNewProduct}
                className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-md border border-dashed border-border-strong px-3 text-[14px] font-medium text-text-2 transition-colors hover:bg-surface-2 hover:text-text"
              >
                <Camera className="size-[17px]" aria-hidden />
                {products.length ? 'Guardar la etiqueta de otro producto' : '¿Un producto envasado? Guarda su etiqueta'}
              </button>
              {recents.length > 0 && (
                <div className="mt-5">
                  <p className="eyebrow">Recientes</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {recents.map((dish) => (
                      <QuickChip key={dish.id} dish={dish} onPick={quickAdd} />
                    ))}
                  </div>
                </div>
              )}
              {dishes.length === 0 && (
                <p className="mt-6 text-center text-[14px] leading-relaxed text-text-3">
                  Lo que vayas apuntando aparecerá aquí para añadirlo con un toque, sin esperas.
                </p>
              )}
            </div>
          ) : phase.kind === 'busy' ? (
            <Analyzing mode={phase.mode} preview={phase.preview} />
          ) : phase.kind === 'fuzzy' ? (
            <div>
              <p className="text-[15px] leading-relaxed text-text-2">
                Se parece mucho a algo que ya tienes. Si es lo mismo, lo añado al momento y sin gastar IA.
              </p>
              <ul className="mt-4 space-y-2.5">
                {phase.candidates.map((candidate) => (
                  <li key={candidate.dish_id} className="card p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[16px] font-semibold tracking-[-0.01em] text-text">{candidate.name}</p>
                        <p className="mt-0.5 truncate text-[13px] text-text-3">«{candidate.matched_text}»</p>
                      </div>
                      <p className="shrink-0 text-[17px] font-semibold text-text" data-num>
                        {fmt(candidate.kcal)} <span className="text-[12.5px] font-medium text-text-3">kcal</span>
                      </p>
                    </div>
                    <MacroBar macros={candidate} className="mt-3" />
                    <div className="mt-2.5 flex items-center justify-between">
                      <MacroInline macros={candidate} />
                      <span className="text-[12px] text-text-3" data-num>
                        {Math.round((candidate.score ?? 0) * 100)} % parecido
                      </span>
                    </div>
                    <Button block className="mt-3.5" onClick={() => save(candidate, { source: 'fuzzy' })} icon={<Check className="size-[18px]" aria-hidden />}>
                      Sí, es esta
                    </Button>
                  </li>
                ))}
              </ul>
              <Button variant="ghost" block className="mt-3" onClick={() => void analyze(text, { skipHistory: true })}>
                No, es otra cosa
              </Button>
            </div>
          ) : phase.kind === 'clarify' ? (
            <div>
              <Notice level="info">{phase.question}</Notice>
              <label htmlFor="meal-detail" className="mt-4 mb-1.5 block text-[13.5px] font-medium text-text-2">
                Cuéntamelo con algo más de detalle
              </label>
              <textarea
                id="meal-detail"
                value={text}
                onChange={(event) => setText(event.target.value)}
                rows={3}
                autoFocus
                className="block w-full resize-none rounded-md border border-border bg-surface-2 px-4 py-3 text-[16px] text-text outline-none focus:border-accent"
              />
              <div className="mt-4 flex gap-3">
                <Button variant="secondary" className="flex-1" onClick={() => setPhase({ kind: 'input' })}>
                  Volver
                </Button>
                <Button className="flex-[2]" onClick={() => void analyze(text, { skipHistory: true })}>
                  Analizar de nuevo
                </Button>
              </div>
            </div>
          ) : phase.kind === 'offline' ? (
            <div className="py-4 text-center">
              <div className="mx-auto grid size-16 place-items-center rounded-full bg-warn-soft">
                <WifiOff className="size-7 text-warn-text" aria-hidden />
              </div>
              <h3 className="mt-4 text-[18px] font-semibold text-text">Esta comida es nueva</h3>
              <p className="mx-auto mt-2 max-w-[32ch] text-[14.5px] leading-relaxed text-text-2">
                Para analizarla necesito conexión. Mientras tanto puedes añadir cualquiera de tu historial, que funciona sin red.
              </p>
              <Button variant="secondary" block className="mt-5" onClick={() => setPhase({ kind: 'input' })}>
                Elegir del historial
              </Button>
              <Button variant="ghost" block className="mt-2" onClick={() => void analyze(text, { skipHistory: true })} icon={<RotateCcw className="size-4" aria-hidden />}>
                Reintentar
              </Button>
            </div>
          ) : (
            <ResultEditor
              draft={phase.draft}
              servings={servings}
              onServings={setServings}
              slot={slot}
              onSlot={setSlot}
              onDraft={(draft) => setPhase({ kind: 'result', draft, via: phase.via })}
              onReanalyze={phase.draft.source === 'cache' || phase.draft.source === 'product' ? () => void analyze(text, { forceAi: true }) : undefined}
              onDiscard={() => setPhase({ kind: 'input' })}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </Sheet>
  )
}

interface ResultProps {
  draft: Draft
  servings: number
  onServings: (value: number) => void
  slot: Slot
  onSlot: (slot: Slot) => void
  onDraft: (draft: Draft) => void
  onReanalyze?: () => void
  onDiscard: () => void
}

function ResultEditor({ draft, servings, onServings, slot, onSlot, onDraft, onReanalyze, onDiscard }: ResultProps) {
  const badge = SOURCE_BADGE[draft.source]
  const confidence = confidenceLabel(draft.confidence)
  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          {badge && (
            <span
              className={clsx(
                'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12.5px] font-semibold',
                badge.saved ? 'bg-accent-soft text-accent-text' : 'bg-protein-soft text-protein-text',
              )}
            >
              <badge.Icon className="size-3.5" aria-hidden />
              {badge.label}
            </span>
          )}
          <span className="inline-flex items-center gap-1.5 text-[12.5px] text-text-3">
            <span className="flex gap-[3px]" aria-hidden>
              {[1, 2, 3].map((n) => (
                <span key={n} className={clsx('h-2.5 w-1 rounded-full', n <= confidence.level ? (confidence.level === 1 ? 'bg-warn' : 'bg-accent') : 'bg-track')} />
              ))}
            </span>
            {confidence.text}
          </span>
        </div>
        <label htmlFor="meal-name" className="sr-only">
          Nombre de la comida
        </label>
        <input
          id="meal-name"
          value={draft.name}
          onChange={(event) => onDraft({ ...draft, name: event.target.value })}
          maxLength={160}
          className="mt-2.5 w-full rounded-sm bg-transparent text-[21px] font-semibold tracking-[-0.02em] text-text outline-none focus:bg-surface-2 focus:px-2"
        />
      </div>

      <Totals items={draft.items} servings={servings} />
      <ServingsPicker value={servings} onChange={onServings} />
      <ItemList items={draft.items} onChange={(items) => onDraft({ ...draft, items })} />

      {draft.assumptions.length > 0 && (
        <div className="rounded-md bg-surface-2 p-3.5">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold text-text-2">
            <Info className="size-3.5" aria-hidden /> He supuesto que…
          </p>
          <ul className="mt-1.5 space-y-1">
            {draft.assumptions.map((assumption) => (
              <li key={assumption} className="flex gap-2 text-[13.5px] leading-snug text-text-2">
                <span className="mt-[7px] size-1 shrink-0 rounded-full bg-text-3" aria-hidden />
                {capitalize(assumption)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <span className="eyebrow">Momento del día</span>
        <div className="mt-2">
          <SlotPicker value={slot} onChange={onSlot} />
        </div>
      </div>

      <div className="flex gap-2">
        <Button variant="ghost" size="sm" onClick={onDiscard} icon={<X className="size-4" aria-hidden />}>
          Descartar
        </Button>
        {onReanalyze && (
          <Button variant="ghost" size="sm" onClick={onReanalyze} icon={<Sparkles className="size-4" aria-hidden />}>
            Analizar con IA
          </Button>
        )}
      </div>
    </div>
  )
}

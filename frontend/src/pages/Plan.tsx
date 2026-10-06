import clsx from 'clsx'
import { motion } from 'motion/react'
import { ChevronLeft, ChevronRight, ClipboardCopy, NotebookPen, Plus, Search, Sparkles, Tag, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { HistoryTabs } from '@/components/HistoryTabs'
import { ServingsPicker } from '@/components/MealBreakdown'
import { useApp, useMealActions, useOnline } from '@/hooks/data'
import { usePlan, usePlanActions } from '@/hooks/plan'
import { api, errorMessage } from '@/lib/api'
import { copyInputs } from '@/lib/copy'
import { addDays, fmtMedium, fmtRange, todayISO, weekStart } from '@/lib/dates'
import { capitalize, fmt, plural } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { GRAM_MACROS, itemsTotal } from '@/lib/macros'
import { singleItem } from '@/lib/products'
import { rankForSlot } from '@/lib/ranking'
import { fmtGrams, shoppingList, type PlanEntry } from '@/lib/shopping'
import { SLOTS } from '@/lib/slots'
import { normalize } from '@/lib/textnorm'
import type { Item, Slot } from '@/lib/types'
import { Button, IconButton } from '@/ui/Button'
import { MacroInline } from '@/ui/MacroBar'
import { Sheet } from '@/ui/Sheet'
import { Skeleton } from '@/ui/Skeleton'
import { toast } from '@/ui/toast'

const PLAN_SLOTS = SLOTS.filter((s) => s.key !== 'snack')
const AI_SLOTS: Slot[] = ['desayuno', 'comida', 'cena']

interface Suggestion {
  date: string
  slot: Slot
  name: string
  items: Item[]
  kcal: number
  protein: number
  carbs: number
  fat: number
}

export default function Plan() {
  const app = useApp()
  const online = useOnline()
  const today = todayISO()
  const [start, setStart] = useState(weekStart(today))
  const plan = usePlan(start)
  const actions = usePlanActions(start)
  const meals = useMealActions()
  const [picking, setPicking] = useState<{ date: string; slot: Slot } | null>(null)
  const [shown, setShown] = useState<PlanEntry | null>(null)
  const [suggestions, setSuggestions] = useState<Suggestion[] | null>(null)
  const [asking, setAsking] = useState(false)
  const entries = useMemo(() => plan.data?.entries ?? [], [plan.data])
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i))
  const list = useMemo(() => shoppingList(entries), [entries])
  const checks = plan.data?.checks ?? {}
  const holes = days
    .filter((d) => d >= today)
    .flatMap((date) => AI_SLOTS.filter((slot) => !entries.some((e) => e.date === date && e.slot === slot)).map((slot) => ({ date, slot })))

  async function askAi() {
    if (!online) return toast.error('Sin conexión', 'Pedir ideas a la IA necesita red.')
    setAsking(true)
    try {
      const reply = await api.post<{ suggestions: Suggestion[] }>('/api/plan/fill', { start, slots: holes.slice(0, 14) })
      setSuggestions(reply.suggestions)
      haptic('success')
    } catch (error) {
      toast.error('No he podido pedir ideas', errorMessage(error))
    } finally {
      setAsking(false)
    }
  }

  function logToDiary(entry: PlanEntry) {
    const [input] = copyInputs(
      [{ ...entry, id: 0, text: '', confidence: 0.8, assumptions: [], source: 'recent', created_at: '' }],
      { date: entry.date, slot: entry.slot },
    )
    meals.add(input)
    haptic('success')
    toast.success('Apuntada en el diario', `${entry.name} · ${capitalize(fmtMedium(entry.date))}`)
    setShown(null)
  }

  async function copyList() {
    const text = list
      .filter((line) => !checks[line.key])
      .map((line) => `- ${line.name}: ${line.units ? `${fmt(line.units.qty, 1)} ${line.units.unit} (${fmtGrams(line.grams)})` : fmtGrams(line.grams)}`)
      .join('\n')
    try {
      await navigator.clipboard.writeText(`Lista de la compra (${fmtRange(start, addDays(start, 6))})\n${text}`)
      toast.success('Lista copiada')
    } catch {
      toast.error('No he podido copiarla')
    }
  }

  return (
    <main className="page">
      <HistoryTabs />
      <header className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-[30px] leading-tight font-semibold tracking-[-0.035em] text-text">Plan semanal</h1>
          <p className="mt-1 text-[14.5px] text-text-2" data-num>
            {start === weekStart(today) ? 'Esta semana' : 'Semana del'} · {fmtRange(start, addDays(start, 6))}
          </p>
        </div>
        <div className="flex shrink-0">
          <IconButton label="Semana anterior" onClick={() => setStart(addDays(start, -7))}>
            <ChevronLeft className="size-5" aria-hidden />
          </IconButton>
          <IconButton label="Semana siguiente" onClick={() => setStart(addDays(start, 7))}>
            <ChevronRight className="size-5" aria-hidden />
          </IconButton>
        </div>
      </header>

      {holes.length > 0 && (
        <Button variant="secondary" block className="mt-4" loading={asking} disabled={!online || !app.ai.configured} onClick={() => void askAi()} icon={<Sparkles className="size-4" aria-hidden />}>
          Pedir ideas a la IA para {holes.length > 14 ? 14 : holes.length} {plural(holes.length, 'hueco', 'huecos')}
        </Button>
      )}

      {plan.isPending ? (
        <Skeleton className="mt-4 h-96 !rounded-[22px]" />
      ) : (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {days.map((date) => {
            const dayEntries = entries.filter((e) => e.date === date)
            const total = dayEntries.reduce((sum, e) => sum + e.kcal, 0)
            const protein = dayEntries.reduce((sum, e) => sum + e.protein, 0)
            const target = plan.data?.targets[date]
            const ratio = target ? Math.min(1, total / target.kcal) : 0
            return (
              <section key={date} className={clsx('card p-4', date === today && 'border-accent')} aria-label={capitalize(fmtMedium(date))}>
                <div className="flex items-baseline justify-between gap-3">
                  <h2 className="text-[15.5px] font-semibold text-text">{capitalize(fmtMedium(date))}</h2>
                  <p className="text-[13px] text-text-2" data-num>
                    <span className="font-semibold text-text">{fmt(total)}</span>
                    {target ? ` de ${fmt(target.kcal)} kcal · P ${fmt(protein)}/${fmt(target.protein)} g` : ' kcal'}
                  </p>
                </div>
                {target && (
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-track" aria-hidden>
                    <motion.div className={clsx('h-full rounded-full', total > target.kcal * 1.1 ? 'bg-danger' : 'bg-kcal')} initial={false} animate={{ width: `${ratio * 100}%` }} />
                  </div>
                )}
                <ul className="mt-2.5 divide-y divide-border">
                  {PLAN_SLOTS.map(({ key, label, Icon }) => {
                    const slotEntries = dayEntries.filter((e) => e.slot === key)
                    return (
                      <li key={key} className="flex items-start gap-2 py-1.5">
                        <Icon className="mt-2.5 size-4 shrink-0 text-text-3" aria-hidden />
                        <div className="min-w-0 flex-1">
                          {slotEntries.length === 0 ? (
                            <p className="py-2 text-[13.5px] text-text-3">{label}</p>
                          ) : (
                            slotEntries.map((entry) => (
                              <button key={entry.client_id} type="button" onClick={() => setShown(entry)} className="flex min-h-11 w-full items-center justify-between gap-2 text-left">
                                <span className="min-w-0 truncate text-[14.5px] text-text">
                                  {entry.name}
                                  {entry.servings !== 1 && <span className="text-text-3" data-num> ×{fmt(entry.servings, 1)}</span>}
                                </span>
                                <span className="shrink-0 text-[13px] text-text-2" data-num>
                                  {fmt(entry.kcal)} kcal
                                </span>
                              </button>
                            ))
                          )}
                        </div>
                        <button type="button" onClick={() => setPicking({ date, slot: key })} aria-label={`Planificar ${label.toLowerCase()} del ${fmtMedium(date)}`} className="grid size-11 shrink-0 place-items-center rounded-full text-text-3 hover:text-accent-text">
                          <Plus className="size-[18px]" aria-hidden />
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </section>
            )
          })}
        </div>
      )}

      <section className="card mt-6 p-4" aria-labelledby="p-shopping">
        <div className="flex items-center justify-between gap-3">
          <h2 id="p-shopping" className="text-[17px] font-semibold text-text">
            Lista de la compra
          </h2>
          {list.length > 0 && (
            <Button variant="ghost" size="sm" onClick={() => void copyList()} icon={<ClipboardCopy className="size-4" aria-hidden />}>
              Copiar
            </Button>
          )}
        </div>
        {list.length === 0 ? (
          <p className="mt-2 text-[14px] text-text-3">Planifica algunas comidas y aquí saldrán sus ingredientes, ya sumados.</p>
        ) : (
          <ul className="mt-2 divide-y divide-border">
            {list.map((line) => (
              <li key={line.key}>
                <label className="flex min-h-11 cursor-pointer items-center gap-3 py-1.5">
                  <input type="checkbox" checked={!!checks[line.key]} onChange={(e) => actions.check(line.key, e.target.checked)} className="size-5 accent-[var(--accent)]" />
                  <span className={clsx('min-w-0 flex-1 text-[14.5px]', checks[line.key] ? 'text-text-3 line-through' : 'text-text')}>{capitalize(line.name)}</span>
                  <span className="shrink-0 text-[13px] text-text-2" data-num>
                    {line.units ? `${fmt(line.units.qty, 1)} ${line.units.unit} · ` : ''}
                    {fmtGrams(line.grams)}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </section>

      <PlanPicker
        target={picking}
        onClose={() => setPicking(null)}
        onPick={(entry) => {
          actions.save(entry)
          haptic('success')
          setPicking(null)
        }}
      />

      <Sheet open={!!shown} onClose={() => setShown(null)} title={shown?.name ?? 'Plan'}>
        {shown && (
          <div className="space-y-4">
            <p className="text-[14px] text-text-2" data-num>
              {capitalize(fmtMedium(shown.date))} · {SLOTS.find((s) => s.key === shown.slot)?.label} · {fmt(shown.kcal)} kcal
            </p>
            <MacroInline macros={shown} />
            <ServingsPicker
              value={shown.servings}
              onChange={(servings) => {
                const next = actions.save({ ...shown, servings })
                setShown(next)
              }}
            />
            <div className="grid grid-cols-2 gap-2.5">
              <Button variant="secondary" size="sm" disabled={shown.date > today} onClick={() => logToDiary(shown)} icon={<NotebookPen className="size-4" aria-hidden />}>
                Apuntar en el diario
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => {
                  actions.remove(shown.client_id)
                  toast({ title: 'Quitada del plan', description: shown.name, action: { label: 'Deshacer', onClick: () => actions.save(shown) } })
                  setShown(null)
                }}
                icon={<Trash2 className="size-4" aria-hidden />}
              >
                Quitar del plan
              </Button>
            </div>
          </div>
        )}
      </Sheet>

      <Sheet open={!!suggestions} onClose={() => setSuggestions(null)} title="Ideas de la IA">
        {suggestions && (
          <div className="space-y-3">
            <p className="text-[13.5px] text-text-2">Elige las que te gusten. Son orientaciones, no consejo médico.</p>
            {suggestions.map((s) => (
              <div key={`${s.date}-${s.slot}`} className="card p-3.5">
                <p className="text-[12.5px] text-text-3">
                  {capitalize(fmtMedium(s.date))} · {SLOTS.find((x) => x.key === s.slot)?.label}
                </p>
                <div className="mt-0.5 flex items-center justify-between gap-3">
                  <p className="min-w-0 text-[15px] font-semibold text-text">{s.name}</p>
                  <p className="shrink-0 text-[14px] font-semibold text-text" data-num>
                    {fmt(s.kcal)} kcal
                  </p>
                </div>
                <MacroInline macros={s} className="mt-1" />
                <Button
                  size="sm"
                  block
                  className="mt-2.5"
                  onClick={() => {
                    actions.save({ date: s.date, slot: s.slot, name: s.name, items: s.items, servings: 1, dish_id: null, source: 'ai' })
                    setSuggestions((list) => (list ?? []).filter((x) => x !== s))
                  }}
                  icon={<Plus className="size-4" aria-hidden />}
                >
                  Añadir al plan
                </Button>
              </div>
            ))}
            {suggestions.length === 0 && <p className="text-[14px] text-text-3">Ya lo has añadido todo.</p>}
          </div>
        )}
      </Sheet>
    </main>
  )
}

function PlanPicker({ target, onClose, onPick }: { target: { date: string; slot: Slot } | null; onClose: () => void; onPick: (entry: Omit<PlanEntry, 'client_id' | 'kcal' | 'protein' | 'carbs' | 'fat'>) => void }) {
  const app = useApp()
  const [query, setQuery] = useState('')
  const slot = target?.slot ?? 'comida'
  const words = normalize(query).split(' ').filter(Boolean)
  const matches = (text: string) => words.every((w) => normalize(text).includes(w))
  const dishes = rankForSlot(app.dishes, slot).filter((d) => matches(d.name)).slice(0, 30)
  const products = app.products.filter((p) => matches(`${p.name} ${p.alias}`)).slice(0, 12)
  return (
    <Sheet open={!!target} onClose={onClose} title={target ? `${SLOTS.find((s) => s.key === slot)?.label} · ${fmtMedium(target.date)}` : 'Planificar'} tall>
      {target && (
        <div className="space-y-3">
          <label className="flex h-12 items-center gap-2.5 rounded-md border border-border bg-surface-2 px-3.5 focus-within:border-accent">
            <Search className="size-[18px] shrink-0 text-text-3" aria-hidden />
            <span className="sr-only">Buscar entre tus comidas</span>
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar entre tus comidas" className="h-full min-w-0 flex-1 bg-transparent text-text outline-none placeholder:text-text-3" />
          </label>
          {dishes.length === 0 && products.length === 0 && (
            <p className="py-6 text-center text-[14px] text-text-3">Lo que vayas apuntando en el diario aparecerá aquí para planificarlo.</p>
          )}
          <ul className="card divide-y divide-border overflow-hidden">
            {dishes.map((dish) => (
              <li key={dish.id}>
                <button
                  type="button"
                  onClick={() => onPick({ date: target.date, slot, name: dish.name, items: dish.items, servings: 1, dish_id: dish.id, source: 'dish' })}
                  className="flex min-h-[52px] w-full items-center gap-3 px-4 py-2 text-left hover:bg-surface-2"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px] text-text">{dish.name}</span>
                    <MacroInline macros={dish} />
                  </span>
                  <span className="shrink-0 text-[14px] font-semibold text-text" data-num>
                    {fmt(dish.kcal)}
                  </span>
                </button>
              </li>
            ))}
            {products.map((product) => {
              const item = singleItem(product)
              return (
                <li key={`p${product.id}`}>
                  <button
                    type="button"
                    onClick={() => onPick({ date: target.date, slot, name: product.alias || product.name, items: [item], servings: 1, dish_id: null, source: 'product' })}
                    className="flex min-h-[52px] w-full items-center gap-3 px-4 py-2 text-left hover:bg-surface-2"
                  >
                    <Tag className="size-4 shrink-0 text-accent-text" aria-hidden />
                    <span className="min-w-0 flex-1 truncate text-[15px] text-text">{product.alias || product.name}</span>
                    <span className="shrink-0 text-[14px] font-semibold text-text" data-num>
                      {fmt(itemsTotal([item]).kcal)}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
          <p className="flex flex-wrap gap-x-3 text-[12px] text-text-3">
            {GRAM_MACROS.map((m) => (
              <span key={m.key}>
                <span className="font-semibold" style={{ color: m.text }}>
                  {m.letter}
                </span>{' '}
                {m.label.toLowerCase()}
              </span>
            ))}
          </p>
        </div>
      )}
    </Sheet>
  )
}

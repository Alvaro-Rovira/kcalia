import { motion } from 'motion/react'
import { ChevronRight, Plus, Search, Tag } from 'lucide-react'
import { useMemo, useState } from 'react'
import { fmt, fmtSmart, plural } from '@/lib/format'
import { normalize } from '@/lib/textnorm'
import type { Product } from '@/lib/types'
import { Button } from '@/ui/Button'
import { EmptyState } from '@/ui/EmptyState'
import { MacroInline } from '@/ui/MacroBar'
import { useShell } from './Shell'

function Thumb({ product }: { product: Product }) {
  return (
    <span className="grid size-[52px] shrink-0 place-items-center overflow-hidden rounded-sm border border-border bg-surface-2">
      {product.has_image ? (
        <img src={`/api/products/${product.id}/image`} alt="" loading="lazy" className="size-full object-cover" />
      ) : (
        <Tag className="size-5 text-text-3" aria-hidden />
      )}
    </span>
  )
}

/** Productos envasados con la foto de su etiqueta: lo que se usa al escribir «dos yogures ligeros». */
export function ProductsLibrary({ products }: { products: Product[] }) {
  const { openProduct } = useShell()
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const words = normalize(query).split(' ').filter(Boolean)
    return products.filter((p) => {
      const hay = normalize(`${p.name} ${p.alias}`)
      return words.every((w) => hay.includes(w))
    })
  }, [products, query])

  return (
    <div>
      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[19px] font-semibold tracking-[-0.02em] text-text">Tus productos</h2>
          <p className="mt-0.5 text-[13.5px] leading-snug text-text-3">Con la foto de su etiqueta: escribe «2 yogures ligeros» y sumo sus calorías exactas.</p>
        </div>
        {products.length > 0 && (
          <Button size="sm" onClick={() => openProduct(null)} icon={<Plus className="size-[18px]" aria-hidden />}>
            Añadir
          </Button>
        )}
      </div>

      {products.length === 0 ? (
        <div className="card mt-3">
          <EmptyState
            art="label"
            title="Aún no tienes productos"
            text="Haz una foto a la parte de atrás de un yogur, unas galletas… y la app guarda sus calorías y macros."
            action={
              <Button onClick={() => openProduct(null)} icon={<Plus className="size-5" aria-hidden />}>
                Guardar una etiqueta
              </Button>
            }
            compact
          />
        </div>
      ) : (
        <>
          {products.length > 5 && (
            <label className="mt-3 flex h-12 items-center gap-2.5 rounded-md border border-border bg-surface-2 px-3.5 focus-within:border-accent">
              <Search className="size-[18px] shrink-0 text-text-3" aria-hidden />
              <span className="sr-only">Buscar entre tus productos</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar entre tus productos"
                enterKeyHint="search"
                className="h-full min-w-0 flex-1 bg-transparent text-text outline-none placeholder:text-text-3"
              />
            </label>
          )}
          {filtered.length === 0 ? (
            <p className="py-8 text-center text-[14.5px] text-text-3">Ningún producto coincide con esa búsqueda.</p>
          ) : (
            <ul className="card mt-3 divide-y divide-border overflow-hidden">
              {filtered.map((product, index) => (
                <motion.li key={product.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index, 8) * 0.03, duration: 0.3 }}>
                  <button type="button" onClick={() => openProduct(product)} className="flex min-h-[76px] w-full items-center gap-3 px-3.5 py-2.5 text-left transition-colors hover:bg-surface-2">
                    <Thumb product={product} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[15px] font-medium text-text">{product.name}</p>
                      <p className="mt-0.5 flex flex-wrap items-center gap-x-2.5 text-[12.5px] text-text-3">
                        <MacroInline macros={{ kcal: product.kcal100, protein: product.protein100, carbs: product.carbs100, fat: product.fat100 }} />
                        <span>por 100 {product.basis}</span>
                      </p>
                      <p className="mt-0.5 truncate text-[12.5px] text-text-3">
                        {product.unit_grams ? `1 ${product.unit_label || 'unidad'} = ${fmtSmart(product.unit_grams)} ${product.basis}` : 'Sin peso por unidad'}
                        {' · '}«{product.alias}»
                        {product.use_count > 0 ? ` · ${product.use_count} ${plural(product.use_count, 'uso', 'usos')}` : ''}
                      </p>
                    </div>
                    <span className="shrink-0 text-right text-[15px] font-semibold text-text" data-num>
                      {fmt(product.kcal100)}
                      <span className="block text-[11.5px] font-medium text-text-3">kcal</span>
                    </span>
                    <ChevronRight className="size-4 shrink-0 text-text-3" aria-hidden />
                  </button>
                </motion.li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

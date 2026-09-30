import { motion, useReducedMotion } from 'motion/react'
import { fmt } from '@/lib/format'
import { GRAM_MACROS, macroSplit } from '@/lib/macros'
import type { Macros } from '@/lib/types'

/** Mini barra apilada con el reparto de calorías entre P, H y G. */
export function MacroBar({ macros, height = 6, className }: { macros: Macros; height?: number; className?: string }) {
  const split = macroSplit(macros)
  const reduce = useReducedMotion()
  const label = GRAM_MACROS.map((m) => `${m.label.toLowerCase()} ${Math.round(split[m.key as 'protein'] * 100)} %`).join(', ')
  return (
    <div
      role="img"
      aria-label={`Reparto de calorías: ${label}`}
      className={`flex w-full gap-[3px] overflow-hidden rounded-full ${className ?? ''}`}
      style={{ height }}
    >
      {GRAM_MACROS.map((m, i) => {
        const share = split[m.key as 'protein']
        return (
          <motion.div
            key={m.key}
            className="h-full rounded-full"
            style={{ background: m.color, minWidth: share > 0 ? 4 : 0 }}
            initial={reduce ? false : { flexGrow: 0 }}
            animate={{ flexGrow: share }}
            transition={reduce ? { duration: 0 } : { duration: 0.7, ease: [0.22, 1, 0.36, 1], delay: i * 0.05 }}
          />
        )
      })}
      {split.protein + split.carbs + split.fat === 0 && <div className="h-full flex-1 rounded-full bg-track" />}
    </div>
  )
}

/** "P 32 · H 45 · G 12": letra con su color + gramos. Siempre en el mismo orden. */
export function MacroInline({ macros, className }: { macros: Macros; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 text-[12.5px] ${className ?? ''}`} data-num>
      {GRAM_MACROS.map((m) => (
        <span key={m.key} className="inline-flex items-baseline gap-1">
          <span className="font-bold" style={{ color: m.text }} aria-hidden>
            {m.letter}
          </span>
          <span className="sr-only">{m.label}:</span>
          <span className="text-text-2">{fmt(macros[m.key])}</span>
        </span>
      ))}
    </span>
  )
}

import { Beef, Droplet, Flame, Wheat, type LucideIcon } from 'lucide-react'
import type { Item, MacroKey, Macros } from './types'

/**
 * Identidad de cada macro en TODA la app: color, letra e icono. El color nunca va solo:
 * la letra (P/H/G) y el icono lo acompañan para que se distinga también con daltonismo.
 */
export interface MacroMeta {
  key: MacroKey
  label: string
  short: string
  letter: string
  unit: string
  color: string
  text: string
  soft: string
  Icon: LucideIcon
}

export const MACROS: Record<MacroKey, MacroMeta> = {
  kcal: {
    key: 'kcal',
    label: 'Calorías',
    short: 'Calorías',
    letter: 'K',
    unit: 'kcal',
    color: 'var(--kcal)',
    text: 'var(--kcal-text)',
    soft: 'var(--kcal-soft)',
    Icon: Flame,
  },
  protein: {
    key: 'protein',
    label: 'Proteínas',
    short: 'Proteína',
    letter: 'P',
    unit: 'g',
    color: 'var(--protein)',
    text: 'var(--protein-text)',
    soft: 'var(--protein-soft)',
    Icon: Beef,
  },
  carbs: {
    key: 'carbs',
    label: 'Hidratos',
    short: 'Hidratos',
    letter: 'H',
    unit: 'g',
    color: 'var(--carbs)',
    text: 'var(--carbs-text)',
    soft: 'var(--carbs-soft)',
    Icon: Wheat,
  },
  fat: {
    key: 'fat',
    label: 'Grasas',
    short: 'Grasas',
    letter: 'G',
    unit: 'g',
    color: 'var(--fat)',
    text: 'var(--fat-text)',
    soft: 'var(--fat-soft)',
    Icon: Droplet,
  },
}

export const GRAM_MACROS: MacroMeta[] = [MACROS.protein, MACROS.carbs, MACROS.fat]
export const KCAL_PER_GRAM: Record<'protein' | 'carbs' | 'fat', number> = { protein: 4, carbs: 4, fat: 9 }

export const ZERO: Macros = { kcal: 0, protein: 0, carbs: 0, fat: 0 }

export function sumMacros(rows: Macros[]): Macros {
  return rows.reduce(
    (acc, row) => ({
      kcal: acc.kcal + row.kcal,
      protein: acc.protein + row.protein,
      carbs: acc.carbs + row.carbs,
      fat: acc.fat + row.fat,
    }),
    { ...ZERO },
  )
}

export function itemsTotal(items: Item[], servings = 1): Macros {
  const total = sumMacros(items)
  const round = (n: number) => Math.round(n * servings * 10) / 10
  return { kcal: round(total.kcal), protein: round(total.protein), carbs: round(total.carbs), fat: round(total.fat) }
}

/** Reparto de las calorías entre los tres macros, en tanto por uno. */
export function macroSplit(m: Macros): Record<'protein' | 'carbs' | 'fat', number> {
  const p = m.protein * 4
  const c = m.carbs * 4
  const f = m.fat * 9
  const total = p + c + f
  if (total <= 0) return { protein: 0, carbs: 0, fat: 0 }
  return { protein: p / total, carbs: c / total, fat: f / total }
}

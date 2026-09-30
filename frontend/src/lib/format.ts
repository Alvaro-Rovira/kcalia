/** Formato es-ES: coma decimal, punto de millares, lunes como primer día. */

const LOCALE = 'es-ES'
const numberFormats = new Map<number, Intl.NumberFormat>()

export function fmt(value: number, decimals = 0): string {
  let format = numberFormats.get(decimals)
  if (!format) {
    format = new Intl.NumberFormat(LOCALE, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
      useGrouping: 'always',
    })
    numberFormats.set(decimals, format)
  }
  // Evita el "-0" que sale al redondear negativos pequeños.
  const rounded = Number(value.toFixed(decimals))
  return format.format(Object.is(rounded, -0) ? 0 : rounded)
}

const smartFormats = new Map<number, Intl.NumberFormat>()

/** Solo los decimales que aportan algo: 80 -> "80", 80,4 -> "80,4", 1,5 con 2 decimales -> "1,5". */
export function fmtSmart(value: number, maxDecimals = 1): string {
  let format = smartFormats.get(maxDecimals)
  if (!format) {
    format = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 0, maximumFractionDigits: maxDecimals, useGrouping: 'always' })
    smartFormats.set(maxDecimals, format)
  }
  const rounded = Number(value.toFixed(maxDecimals))
  return format.format(Object.is(rounded, -0) ? 0 : rounded)
}

export function fmtSigned(value: number, decimals = 0): string {
  const text = fmt(Math.abs(value), decimals)
  if (Number(value.toFixed(decimals)) === 0) return text
  return (value > 0 ? '+' : '−') + text
}

/** Acepta "72,5" y "72.5". Devuelve NaN si no es un número. */
export function parseNumber(text: string): number {
  const clean = text.trim().replace(/\s/g, '').replace(',', '.')
  return clean === '' ? NaN : Number(clean)
}

export function capitalize(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text
}

export function plural(n: number, one: string, many: string): string {
  return Math.abs(n) === 1 ? one : many
}

const KG_PER_LB = 0.45359237

export function kgTo(unit: 'kg' | 'lb', kg: number): number {
  return unit === 'lb' ? kg / KG_PER_LB : kg
}

export function toKg(unit: 'kg' | 'lb', value: number): number {
  return unit === 'lb' ? value * KG_PER_LB : value
}

const LOCALE = 'es-ES'

export function toISO(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function parseISO(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function todayISO(): string {
  return toISO(new Date())
}

export function isValidISO(iso: string | null | undefined): iso is string {
  return !!iso && /^\d{4}-\d{2}-\d{2}$/.test(iso) && toISO(parseISO(iso)) === iso
}

export function addDays(iso: string, days: number): string {
  const date = parseISO(iso)
  date.setDate(date.getDate() + days)
  return toISO(date)
}

export function diffDays(a: string, b: string): number {
  return Math.round((parseISO(a).getTime() - parseISO(b).getTime()) / 86_400_000)
}

/** Lunes de la semana (la semana empieza en lunes). */
export function weekStart(iso: string): string {
  const date = parseISO(iso)
  const weekday = (date.getDay() + 6) % 7
  return addDays(iso, -weekday)
}

const formats = {
  long: new Intl.DateTimeFormat(LOCALE, { weekday: 'long', day: 'numeric', month: 'long' }),
  medium: new Intl.DateTimeFormat(LOCALE, { weekday: 'short', day: 'numeric', month: 'short' }),
  short: new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'short' }),
  weekday: new Intl.DateTimeFormat(LOCALE, { weekday: 'long' }),
  weekdayShort: new Intl.DateTimeFormat(LOCALE, { weekday: 'short' }),
  monthYear: new Intl.DateTimeFormat(LOCALE, { month: 'long', year: 'numeric' }),
}

const clean = (text: string) => text.replace(/\./g, '')

export const fmtLong = (iso: string) => formats.long.format(parseISO(iso))
export const fmtMedium = (iso: string) => clean(formats.medium.format(parseISO(iso)))
export const fmtShort = (iso: string) => clean(formats.short.format(parseISO(iso)))
export const fmtWeekday = (iso: string) => formats.weekday.format(parseISO(iso))
export const fmtWeekdayShort = (iso: string) => clean(formats.weekdayShort.format(parseISO(iso)))
export const fmtMonthYear = (iso: string) => formats.monthYear.format(parseISO(iso))
/** Inicial del día: L M X J V S D (la X del miércoles evita confundirlo con el martes). */
export const weekdayInitial = (iso: string) => 'DLMXJVS'[parseISO(iso).getDay()]

export function relativeDay(iso: string, today = todayISO()): string {
  const delta = diffDays(iso, today)
  if (delta === 0) return 'Hoy'
  if (delta === -1) return 'Ayer'
  if (delta === 1) return 'Mañana'
  if (delta === -2) return 'Anteayer'
  return fmtMedium(iso)
}

export function fmtRange(start: string, end: string): string {
  const a = parseISO(start)
  const b = parseISO(end)
  if (a.getMonth() === b.getMonth()) return `${a.getDate()} – ${fmtShort(end)}`
  return `${fmtShort(start)} – ${fmtShort(end)}`
}

export function greeting(now = new Date()): string {
  const hour = now.getHours()
  if (hour >= 6 && hour < 13) return 'Buenos días'
  if (hour >= 13 && hour < 21) return 'Buenas tardes'
  return 'Buenas noches'
}

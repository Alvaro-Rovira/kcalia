/**
 * Espejo de backend/app/textnorm.py y de la parte de coincidencias de matching.py.
 * Sirve para resolver comidas del historial sin conexión (y sin esperar al servidor).
 * Ambos lados se prueban contra backend/tests/fixtures/normalize_cases.json.
 */

const ARTICLES = new Set(['el', 'la', 'los', 'las', 'un', 'una', 'uno', 'unos', 'unas', 'de', 'del'])

const NUMBER_WORDS: Record<string, string> = {
  medio: '0.5',
  media: '0.5',
  par: '2',
  dos: '2',
  tres: '3',
  cuatro: '4',
  cinco: '5',
  seis: '6',
  siete: '7',
  ocho: '8',
  nueve: '9',
  diez: '10',
  once: '11',
  doce: '12',
}

const UNIT_GROUPS: Record<string, string[]> = {
  g: ['g', 'gr', 'grs', 'gramo', 'gramos'],
  kg: ['kg', 'kilo', 'kilos', 'kilogramo', 'kilogramos'],
  ml: ['ml', 'mililitro', 'mililitros'],
  cl: ['cl', 'centilitro', 'centilitros'],
  l: ['l', 'litro', 'litros'],
  cda: ['cda', 'cdas', 'cucharada', 'cucharadas'],
  cdta: ['cdta', 'cdtas', 'cucharadita', 'cucharaditas'],
  vaso: ['vaso', 'vasos'],
  taza: ['taza', 'tazas'],
  rebanada: ['rebanada', 'rebanadas'],
  loncha: ['loncha', 'lonchas'],
  lata: ['lata', 'latas'],
  puñado: ['puñado', 'puñados'],
  plato: ['plato', 'platos'],
  racion: ['racion', 'raciones'],
  pieza: ['pieza', 'piezas', 'unidad', 'unidades', 'ud', 'uds'],
  bol: ['bol', 'boles', 'cuenco', 'cuencos'],
  cazo: ['cazo', 'cazos', 'scoop', 'scoops'],
}
const UNITS = new Map<string, string>()
for (const [unit, aliases] of Object.entries(UNIT_GROUPS)) for (const alias of aliases) UNITS.set(alias, unit)

const VULGAR: Record<string, string> = { '½': ' 0.5 ', '¼': ' 0.25 ', '¾': ' 0.75 ' }
const NUMBER = /^\d+(\.\d+)?$/

export const SIMILARITY_THRESHOLD = 0.85
const TOKEN_THRESHOLD = 0.75
const CONNECTORS = new Set(['con', 'y', 'e', 'a', 'al', 'en'])

function stripAccents(text: string): string {
  return text
    .replace(/ñ/gi, '\u0000')
    .normalize('NFD')
    .replace(/\p{Mn}/gu, '')
    .replace(/\u0000/g, 'ñ')
}

function formatNumber(value: number): string {
  return value
    .toFixed(3)
    .replace(/0+$/, '')
    .replace(/\.$/, '')
}

const isNumber = (token: string) => NUMBER.test(token)

function baseTokens(input: string): string[] {
  let text = input.toLowerCase()
  for (const [char, replacement] of Object.entries(VULGAR)) text = text.split(char).join(replacement)
  text = stripAccents(text)
  text = text.replace(/(\d+)\s*\/\s*(\d+)/g, (match, a, b) => (Number(b) ? formatNumber(Number(a) / Number(b)) : match))
  text = text.replace(/(?<=\d),(?=\d)/g, '.')
  text = text.replace(/(\d)([a-zñ])/g, '$1 $2')
  text = text.replace(/([a-zñ])(\d)/g, '$1 $2')
  text = text.replace(/[^a-z0-9ñ. ]/g, ' ')
  text = text.replace(/(?<!\d)\.|\.(?!\d)/g, ' ')
  return text
    .split(/\s+/)
    .filter(Boolean)
    .map((raw) => {
      let token = isNumber(raw) ? formatNumber(Number(raw)) : raw
      token = NUMBER_WORDS[token] ?? token
      return UNITS.get(token) ?? token
    })
}

export function normalize(text: string): string {
  const tokens = baseTokens(text).filter((t) => !ARTICLES.has(t))
  const out: string[] = []
  tokens.forEach((token, i) => {
    const next = tokens[i + 1]
    if (token === '1' && next !== undefined && !isNumber(next) && !(next in UNIT_GROUPS)) return
    out.push(token)
  })
  return out.join(' ')
}

export function numbersIn(norm: string): string[] {
  return norm.split(' ').filter(isNumber).sort()
}

function singular(token: string): string {
  if (token.length <= 3 || isNumber(token)) return token
  if (token.endsWith('ces')) return token.slice(0, -3) + 'z'
  if (token.endsWith('es') && 'lrndjsz'.includes(token[token.length - 3])) return token.slice(0, -2)
  if (token.endsWith('s') && !token.endsWith('ss')) return token.slice(0, -1)
  return token
}

export function foodKey(name: string): string {
  return normalize(name).split(' ').filter(Boolean).map(singular).join(' ')
}

export function splitParts(text: string): string[] {
  return text
    .split(/[,;+\n]|\s+(?:y|e|mas|más)\s+/i)
    .map((p) => p?.trim())
    .filter(Boolean)
}

export function parsePart(part: string): [number, string | null, string] {
  let raw = baseTokens(part)
  let qty: number | null = null
  if (raw.length && ['un', 'una', 'uno'].includes(raw[0])) {
    qty = 1
    raw = raw.slice(1)
  }
  let tokens = raw.filter((t) => !ARTICLES.has(t))
  let unit: string | null = null
  if (tokens.length && isNumber(tokens[0])) {
    qty = Number(tokens[0])
    tokens = tokens.slice(1)
    if (tokens.length && tokens[0] in UNIT_GROUPS) {
      unit = tokens[0]
      tokens = tokens.slice(1)
    }
  } else if (tokens.length >= 3 && isNumber(tokens[tokens.length - 2]) && tokens[tokens.length - 1] in UNIT_GROUPS) {
    qty = Number(tokens[tokens.length - 2])
    unit = tokens[tokens.length - 1]
    tokens = tokens.slice(0, -2)
  } else if (tokens.length > 1 && tokens[0] in UNIT_GROUPS) {
    unit = tokens[0]
    tokens = tokens.slice(1)
  }
  return [qty ?? 1, unit, tokens.map(singular).join(' ')]
}

/** Longitud de la subsecuencia común más larga. */
function lcs(a: string, b: string): number {
  if (!a.length || !b.length) return 0
  let prev = new Array<number>(b.length + 1).fill(0)
  for (let i = 1; i <= a.length; i++) {
    const row = new Array<number>(b.length + 1).fill(0)
    for (let j = 1; j <= b.length; j++) {
      row[j] = a[i - 1] === b[j - 1] ? prev[j - 1] + 1 : Math.max(prev[j], row[j - 1])
    }
    prev = row
  }
  return prev[b.length]
}

/** Igual que rapidfuzz.fuzz.ratio: similitud Indel normalizada, 0..1. */
function ratio(a: string, b: string): number {
  const total = a.length + b.length
  return total === 0 ? 1 : (2 * lcs(a, b)) / total
}

const sortTokens = (text: string) => text.split(' ').filter(Boolean).sort().join(' ')

export function similarity(a: string, b: string): number {
  if (!a || !b) return 0
  return Math.max(ratio(a, b), ratio(sortTokens(a), sortTokens(b)))
}

function tokensAligned(a: string, b: string): boolean {
  const left = a.split(' ').filter((t) => t && !CONNECTORS.has(t))
  const right = b.split(' ').filter((t) => t && !CONNECTORS.has(t))
  const covered = (tokens: string[], others: string[]) =>
    tokens.every((t) => others.some((o) => ratio(t, o) >= TOKEN_THRESHOLD))
  return left.length > 0 && right.length > 0 && covered(left, right) && covered(right, left)
}

export function findSimilar<T>(
  norm: string,
  candidates: Iterable<[T, string]>,
  threshold = SIMILARITY_THRESHOLD,
  limit = 3,
): [T, number][] {
  const wanted = numbersIn(norm).join(',')
  const scored: [T, number][] = []
  for (const [id, candidate] of candidates) {
    if (candidate === norm) continue
    const score = similarity(norm, candidate)
    if (score >= threshold && numbersIn(candidate).join(',') === wanted && tokensAligned(norm, candidate)) {
      scored.push([id, Math.round(score * 1000) / 1000])
    }
  }
  return scored.sort((x, y) => y[1] - x[1]).slice(0, limit)
}

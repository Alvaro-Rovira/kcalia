/** Imagen del resumen semanal para compartir: se dibuja en un canvas con los colores del tema (tokens.css). */
import { addDays, fmtRange, weekdayInitial } from './dates'
import { fmt, fmtSigned } from './format'
import type { WeekSummary } from './types'

const W = 1080
const H = 1350

export interface ShareLine {
  label: string
  value: string
}

/** Las cifras que salen en la imagen (y en el texto alternativo al compartir). */
export function shareLines(s: WeekSummary): ShareLine[] {
  const lines: ShareLine[] = [
    { label: 'Adherencia', value: `${s.adherence_pct} %` },
    { label: 'Media diaria', value: `${fmt(s.avg_kcal)} kcal` },
    { label: 'Proteína media', value: `${fmt(s.avg_protein)} g` },
    { label: 'Días registrados', value: `${s.logged_days} de 7` },
  ]
  if (s.weight.change !== null) lines.push({ label: 'Peso', value: `${fmtSigned(s.weight.change, 1)} kg` })
  else if (s.weight.avg !== null) lines.push({ label: 'Peso medio', value: `${fmt(s.weight.avg, 1)} kg` })
  return lines
}

export function shareText(s: WeekSummary): string {
  return `Mi semana con Kcalia (${fmtRange(s.week_start, s.week_end)}): ${shareLines(s)
    .map((l) => `${l.label.toLowerCase()} ${l.value}`)
    .join(', ')}.`
}

function token(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, radius: number) {
  const r = Math.min(radius, h / 2, w / 2)
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

/** Dibuja la tarjeta y devuelve el PNG. */
export async function renderShareCard(s: WeekSummary): Promise<Blob> {
  await document.fonts?.ready
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas')
  const c = {
    bg: token('--bg', '#0b0c0e'),
    surface: token('--surface', '#14161a'),
    text: token('--text', '#f4f5f7'),
    text2: token('--text-2', '#aab0bb'),
    text3: token('--text-3', '#838a97'),
    accent: token('--accent', '#34d399'),
    accentText: token('--accent-text', '#4ade9f'),
    kcal: token('--kcal', '#34d399'),
    over: token('--kcal-over', '#ff6b6b'),
    low: token('--warn', '#f5b84f'),
    track: token('--surface-3', '#262a31'),
    border: token('--border-strong', 'rgba(255,255,255,0.15)'),
  }
  const font = (weight: number, size: number) => `${weight} ${size}px 'Geist Variable', ui-sans-serif, system-ui, sans-serif`

  ctx.fillStyle = c.bg
  ctx.fillRect(0, 0, W, H)

  // Cabecera: marca y semana.
  ctx.fillStyle = c.accentText
  ctx.font = font(700, 56)
  ctx.fillText('k', 80, 140)
  const k = ctx.measureText('k').width
  ctx.fillStyle = c.text
  ctx.fillText('calia', 80 + k, 140)
  ctx.fillStyle = c.text2
  ctx.font = font(500, 34)
  ctx.fillText(`Mi semana · ${fmtRange(s.week_start, s.week_end)}`, 80, 200)

  // Cifra principal: adherencia.
  ctx.fillStyle = c.text
  ctx.font = font(650, 200)
  ctx.fillText(`${s.adherence_pct} %`, 72, 420)
  ctx.fillStyle = c.text2
  ctx.font = font(500, 36)
  ctx.fillText(`de días en objetivo · ${s.on_target_days} de ${s.days_elapsed}`, 80, 480)

  // Barras de la semana, con el mismo código de color que la app (y la inicial del día debajo).
  const top = 540
  const height = 280
  const max = Math.max(s.targets.kcal * 1.25, ...s.days.map((d) => d.kcal))
  const slot = (W - 160) / 7
  s.days.forEach((day, i) => {
    const x = 80 + i * slot + slot * 0.2
    const w = slot * 0.6
    const h = day.logged ? Math.max(12, (day.kcal / max) * height) : 8
    ctx.fillStyle = day.status === 'cumplido' ? c.kcal : day.status === 'pasado' ? c.over : day.status === 'bajo' ? c.low : c.track
    roundRect(ctx, x, top + height - h, w, h, 10)
    ctx.fill()
    ctx.fillStyle = c.text3
    ctx.font = font(600, 30)
    ctx.textAlign = 'center'
    ctx.fillText(weekdayInitial(addDays(s.week_start, i)), x + w / 2, top + height + 48)
    ctx.textAlign = 'left'
  })
  const targetY = top + height - (s.targets.kcal / max) * height
  ctx.strokeStyle = c.text2
  ctx.setLineDash([10, 10])
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(80, targetY)
  ctx.lineTo(W - 80, targetY)
  ctx.stroke()
  ctx.setLineDash([])
  ctx.fillStyle = c.text2
  ctx.font = font(500, 26)
  ctx.textAlign = 'right'
  ctx.fillText(`Objetivo ${fmt(s.targets.kcal)} kcal`, W - 80, targetY - 14)
  ctx.textAlign = 'left'

  // Leyenda: el color nunca va solo.
  let legendX = 80
  for (const [color, text] of [
    [c.kcal, 'En objetivo'],
    [c.low, 'Por debajo'],
    [c.over, 'Por encima'],
  ] as const) {
    ctx.fillStyle = color
    roundRect(ctx, legendX, top + height + 78, 22, 22, 6)
    ctx.fill()
    ctx.fillStyle = c.text2
    ctx.font = font(500, 26)
    ctx.fillText(text, legendX + 34, top + height + 98)
    legendX += 34 + ctx.measureText(text).width + 40
  }

  // Cifras clave.
  const lines = shareLines(s).slice(1)
  const boxTop = 1010
  const boxW = (W - 160 - 24) / 2
  lines.slice(0, 4).forEach((line, i) => {
    const x = 80 + (i % 2) * (boxW + 24)
    const y = boxTop + Math.floor(i / 2) * 140
    ctx.fillStyle = c.surface
    roundRect(ctx, x, y, boxW, 122, 28)
    ctx.fill()
    ctx.fillStyle = c.text3
    ctx.font = font(500, 28)
    ctx.fillText(line.label, x + 32, y + 46)
    ctx.fillStyle = c.text
    ctx.font = font(650, 44)
    ctx.fillText(line.value, x + 32, y + 98)
  })

  ctx.fillStyle = c.text3
  ctx.font = font(500, 26)
  ctx.fillText('Calorías y macros, con calma', 80, H - 40)

  return await new Promise<Blob>((resolve, reject) => canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('blob'))), 'image/png'))
}

/** Comparte con el menú del sistema (Web Share) o, si no se puede, descarga la imagen. */
export async function shareSummary(s: WeekSummary): Promise<'shared' | 'downloaded' | 'cancelled'> {
  const blob = await renderShareCard(s)
  const file = new File([blob], `kcalia-semana-${s.week_start}.png`, { type: 'image/png' })
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: 'Mi semana con Kcalia', text: shareText(s) })
      return 'shared'
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return 'cancelled'
    }
  }
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = file.name
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
  return 'downloaded'
}

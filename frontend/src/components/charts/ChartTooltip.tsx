import type { ReactNode } from 'react'

/** Marco común de los tooltips: el valor manda y la etiqueta acompaña. */
export function TooltipCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="glass min-w-[148px] rounded-md px-3 py-2.5 shadow-lg">
      <p className="text-[12px] font-medium text-text-2">{title}</p>
      <div className="mt-1.5 space-y-1">{children}</div>
    </div>
  )
}

/** Fila con clave de línea (no caja) del color de la serie. */
export function TooltipRow({ color, label, value }: { color?: string; label: string; value: string }) {
  return (
    <p className="flex items-center justify-between gap-4 text-[13px]">
      <span className="flex items-center gap-1.5 text-text-2">
        {color && <span className="h-[3px] w-3 rounded-full" style={{ background: color }} aria-hidden />}
        {label}
      </span>
      <span className="font-semibold text-text" data-num>
        {value}
      </span>
    </p>
  )
}

export function LegendItem({ color, label, shape = 'rect' }: { color: string; label: string; shape?: 'rect' | 'line' | 'dot' }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[12.5px] text-text-2">
      <span
        aria-hidden
        className={shape === 'rect' ? 'size-2.5 rounded-[3px]' : shape === 'dot' ? 'size-2 rounded-full' : 'h-[3px] w-3.5 rounded-full'}
        style={{ background: color }}
      />
      {label}
    </span>
  )
}

export const AXIS_TICK = { fill: 'var(--text-3)', fontSize: 11.5, fontFamily: 'inherit' }
export const GRID_STROKE = 'var(--border)'

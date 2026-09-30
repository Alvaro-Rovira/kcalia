import type { ReactNode } from 'react'

type Art = 'plate' | 'chart' | 'scale' | 'book' | 'offline' | 'lost'

/** Ilustraciones de línea hechas con los colores de los macros. */
function Illustration({ art }: { art: Art }) {
  const common = { fill: 'none', strokeWidth: 2.5, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  return (
    <svg viewBox="0 0 160 120" className="h-[120px] w-[160px]" aria-hidden>
      <ellipse cx="80" cy="104" rx="54" ry="6" fill="var(--surface-2)" />
      {art === 'plate' && (
        <g {...common}>
          <circle cx="80" cy="60" r="34" stroke="var(--border-strong)" />
          <circle cx="80" cy="60" r="22" stroke="var(--kcal)" strokeDasharray="92 140" transform="rotate(-90 80 60)" />
          <path d="M30 34v20m-5-20v10a5 5 0 0 0 10 0V34m-5 20v32" stroke="var(--protein)" />
          <path d="M130 34c-6 4-8 12-8 20h8m0-20v52" stroke="var(--fat)" />
          <circle cx="80" cy="60" r="3" fill="var(--carbs)" stroke="none" />
        </g>
      )}
      {art === 'chart' && (
        <g {...common}>
          <path d="M34 92h92" stroke="var(--border-strong)" />
          <rect x="44" y="62" width="14" height="30" rx="4" stroke="var(--protein)" />
          <rect x="66" y="44" width="14" height="48" rx="4" stroke="var(--kcal)" />
          <rect x="88" y="54" width="14" height="38" rx="4" stroke="var(--carbs)" />
          <rect x="110" y="34" width="14" height="58" rx="4" stroke="var(--fat)" />
          <path d="M38 50h88" stroke="var(--text-3)" strokeDasharray="3 7" />
        </g>
      )}
      {art === 'scale' && (
        <g {...common}>
          <rect x="40" y="34" width="80" height="62" rx="16" stroke="var(--border-strong)" />
          <path d="M60 60a20 20 0 0 1 40 0" stroke="var(--kcal)" />
          <path d="M80 60l9-10" stroke="var(--fat)" />
          <circle cx="80" cy="60" r="2.5" fill="var(--text-2)" stroke="none" />
          <path d="M66 80h28" stroke="var(--protein)" />
        </g>
      )}
      {art === 'book' && (
        <g {...common}>
          <path d="M80 38c-10-7-24-8-36-5v54c12-3 26-2 36 5 10-7 24-8 36-5V33c-12-3-26-2-36 5Z" stroke="var(--border-strong)" />
          <path d="M80 38v54" stroke="var(--border-strong)" />
          <path d="M54 50h16M54 62h16" stroke="var(--protein)" />
          <path d="M90 50h16" stroke="var(--carbs)" />
          <path d="M90 62h10" stroke="var(--fat)" />
          <path d="M96 78l5 5 9-11" stroke="var(--kcal)" />
        </g>
      )}
      {art === 'offline' && (
        <g {...common}>
          <path d="M44 56a52 52 0 0 1 72 0" stroke="var(--border-strong)" />
          <path d="M56 68a34 34 0 0 1 48 0" stroke="var(--carbs)" />
          <path d="M68 80a17 17 0 0 1 24 0" stroke="var(--kcal)" />
          <circle cx="80" cy="92" r="3" fill="var(--kcal)" stroke="none" />
          <path d="M48 34l64 64" stroke="var(--fat)" />
        </g>
      )}
      {art === 'lost' && (
        <g {...common}>
          <circle cx="80" cy="58" r="32" stroke="var(--border-strong)" />
          <path d="M92 46 86 66 68 72l6-20Z" stroke="var(--kcal)" />
          <circle cx="80" cy="58" r="2.5" fill="var(--fat)" stroke="none" />
          <path d="M80 22v6M80 88v6M44 58h6M110 58h6" stroke="var(--protein)" />
        </g>
      )}
    </svg>
  )
}

interface Props {
  art: Art
  title: string
  text?: string
  action?: ReactNode
  compact?: boolean
}

export function EmptyState({ art, title, text, action, compact }: Props) {
  return (
    <div className={`flex flex-col items-center text-center ${compact ? 'py-6' : 'py-10'}`}>
      <Illustration art={art} />
      <h3 className="mt-3 text-[17px] font-semibold tracking-[-0.01em] text-text">{title}</h3>
      {text && <p className="mt-1.5 max-w-[30ch] text-[14.5px] leading-relaxed text-text-2">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

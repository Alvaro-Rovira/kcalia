import { motion, useReducedMotion } from 'motion/react'
import { useId, type ReactNode } from 'react'

interface Props {
  /** Progreso en tanto por uno. Por encima de 1 se dibuja el exceso en otra vuelta. */
  progress: number
  size: number
  stroke: number
  color: string
  /** Color del arranque del trazo: con él, el anillo va de `from` al color según avanza. */
  from?: string
  overColor?: string
  label: string
  children?: ReactNode
  glow?: boolean
  delay?: number
  className?: string
}

const EASE = [0.22, 1, 0.36, 1] as const

export function Ring({
  progress,
  size,
  stroke,
  color,
  from,
  overColor = 'var(--kcal-over)',
  label,
  children,
  glow,
  delay = 0,
  className,
}: Props) {
  const id = useId()
  const reduce = useReducedMotion()
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const safe = Number.isFinite(progress) ? Math.max(0, progress) : 0
  const main = Math.min(1, safe)
  const over = Math.min(1, Math.max(0, safe - 1))
  const transition = reduce ? { duration: 0 } : { duration: 1.1, ease: EASE, delay }
  // El extremo del degradado se acerca al color final conforme avanza el progreso.
  const endMix = Math.round(main * 100)

  return (
    <div
      role="img"
      aria-label={label}
      className={`relative grid shrink-0 place-items-center ${className ?? ''}`}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="-rotate-90"
        style={glow && main > 0.02 ? { filter: 'var(--ring-glow)' } : undefined}
        aria-hidden
      >
        {from && (
          <defs>
            <linearGradient id={id} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style={{ stopColor: from }} />
              <stop offset="100%" style={{ stopColor: `color-mix(in oklab, ${color} ${endMix}%, ${from})` }} />
            </linearGradient>
          </defs>
        )}
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--track)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={from ? `url(#${id})` : color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - main) }}
          transition={transition}
          style={{ opacity: main > 0 ? 1 : 0 }}
        />
        {over > 0 && (
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={overColor}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - over) }}
            transition={{ ...transition, delay: reduce ? 0 : delay + 0.5 }}
          />
        )}
      </svg>
      {children && <div className="absolute inset-0 grid place-items-center">{children}</div>}
    </div>
  )
}

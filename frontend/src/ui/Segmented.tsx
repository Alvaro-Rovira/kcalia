import clsx from 'clsx'
import { motion } from 'motion/react'
import { useId, type ReactNode } from 'react'
import { haptic } from '@/lib/haptics'

interface Option<T extends string> {
  value: T
  label: ReactNode
  ariaLabel?: string
}

interface Props<T extends string> {
  options: Option<T>[]
  value: T
  onChange: (value: T) => void
  label: string
  size?: 'md' | 'sm'
  className?: string
}

/** Selector segmentado con el indicador deslizándose entre opciones. */
export function Segmented<T extends string>({ options, value, onChange, label, size = 'md', className }: Props<T>) {
  const id = useId()
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={clsx('flex rounded-md border border-border bg-surface-2 p-1', className)}
    >
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={option.ariaLabel}
            onClick={() => {
              if (!active) {
                haptic('select')
                onChange(option.value)
              }
            }}
            className={clsx(
              'relative flex min-w-0 flex-1 items-center justify-center gap-1.5 rounded-[11px] px-2 font-medium transition-colors',
              size === 'md' ? 'h-11 text-[14.5px]' : 'h-11 text-[13.5px]',
              active ? 'text-text' : 'text-text-3 hover:text-text-2',
            )}
          >
            {active && (
              <motion.span
                layoutId={`seg-${id}`}
                className="absolute inset-0 rounded-[11px] border border-border bg-surface shadow-sm"
                transition={{ type: 'spring', stiffness: 520, damping: 40 }}
              />
            )}
            <span className="relative flex items-center gap-1.5 truncate">{option.label}</span>
          </button>
        )
      })}
    </div>
  )
}

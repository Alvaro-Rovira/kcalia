import clsx from 'clsx'
import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import { haptic } from '@/lib/haptics'

interface Props {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description?: ReactNode
  disabled?: boolean
}

/** Interruptor con su etiqueta: toda la fila se puede pulsar (mínimo táctil de 44 px). */
export function Switch({ checked, onChange, label, description, disabled }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => {
        haptic('select')
        onChange(!checked)
      }}
      className="flex min-h-[52px] w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-surface-2 disabled:opacity-50"
    >
      <span className="min-w-0 flex-1">
        <span className="block text-[15px] text-text">{label}</span>
        {description && <span className="mt-0.5 block text-[13px] leading-snug text-text-3">{description}</span>}
      </span>
      <span
        aria-hidden
        className={clsx('relative h-[30px] w-[50px] shrink-0 rounded-full border transition-colors', checked ? 'border-accent bg-accent' : 'border-border-strong bg-surface-3')}
      >
        <motion.span
          className="absolute top-[3px] left-[3px] size-[22px] rounded-full bg-surface shadow-sm"
          animate={{ x: checked ? 20 : 0 }}
          transition={{ type: 'spring', stiffness: 600, damping: 36 }}
        />
      </span>
    </button>
  )
}

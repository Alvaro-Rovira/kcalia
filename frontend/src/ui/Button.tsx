import clsx from 'clsx'
import { motion, type HTMLMotionProps } from 'motion/react'
import { Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { haptic } from '@/lib/haptics'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
type Size = 'lg' | 'md' | 'sm'

interface Props extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?: Variant
  size?: Size
  loading?: boolean
  block?: boolean
  icon?: ReactNode
  children?: ReactNode
}

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-on-accent shadow-md hover:bg-accent-strong',
  secondary: 'bg-surface-2 text-text border border-border hover:bg-surface-3',
  outline: 'border border-border-strong text-text hover:bg-surface-2',
  ghost: 'text-text-2 hover:bg-surface-2 hover:text-text',
  danger: 'bg-danger-soft text-danger-text hover:brightness-110',
}

// Todas las alturas respetan el mínimo táctil de 44 px.
const SIZES: Record<Size, string> = {
  lg: 'h-14 px-6 text-[16px] rounded-md gap-2.5',
  md: 'h-12 px-5 text-[15px] rounded-md gap-2',
  sm: 'h-11 px-4 text-[14px] rounded-sm gap-1.5',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  block,
  icon,
  children,
  className,
  disabled,
  onClick,
  type = 'button',
  ...rest
}: Props) {
  return (
    <motion.button
      type={type}
      whileTap={disabled || loading ? undefined : { scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 600, damping: 32 }}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      onClick={(event) => {
        haptic('tap')
        onClick?.(event)
      }}
      className={clsx(
        'inline-flex shrink-0 items-center justify-center font-semibold tracking-[-0.01em] transition-colors duration-150 select-none',
        'disabled:opacity-45',
        VARIANTS[variant],
        SIZES[size],
        block && 'w-full',
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="size-[18px] animate-spin" aria-hidden /> : icon}
      {children}
    </motion.button>
  )
}

interface IconButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  label: string
  children: ReactNode
  tone?: 'default' | 'surface'
}

export function IconButton({ label, children, className, tone = 'default', onClick, type = 'button', ...rest }: IconButtonProps) {
  return (
    <motion.button
      type={type}
      aria-label={label}
      title={label}
      whileTap={{ scale: 0.9 }}
      transition={{ type: 'spring', stiffness: 600, damping: 30 }}
      onClick={(event) => {
        haptic('tap')
        onClick?.(event)
      }}
      className={clsx(
        'grid size-11 shrink-0 place-items-center rounded-full text-text-2 transition-colors hover:text-text disabled:opacity-40',
        tone === 'surface' ? 'border border-border bg-surface' : 'hover:bg-surface-2',
        className,
      )}
      {...rest}
    >
      {children}
    </motion.button>
  )
}

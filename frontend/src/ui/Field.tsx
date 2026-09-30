import clsx from 'clsx'
import { Minus, Plus } from 'lucide-react'
import { useEffect, useId, useState, type InputHTMLAttributes, type ReactNode } from 'react'
import { fmtSmart, parseNumber } from '@/lib/format'
import { haptic } from '@/lib/haptics'

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
  error?: string
  suffix?: ReactNode
}

export function Field({ label, hint, error, suffix, className, id, ...rest }: FieldProps) {
  const auto = useId()
  const fieldId = id ?? auto
  const describedBy = error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined
  return (
    <div className={className}>
      <label htmlFor={fieldId} className="mb-1.5 block text-[13.5px] font-medium text-text-2">
        {label}
      </label>
      <div
        className={clsx(
          'flex h-13 items-center rounded-md border bg-surface-2 px-4 transition-colors focus-within:border-accent',
          error ? 'border-danger' : 'border-border',
        )}
      >
        <input
          id={fieldId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className="h-full min-w-0 flex-1 bg-transparent text-text outline-none placeholder:text-text-3"
          {...rest}
        />
        {suffix && <span className="ml-2 shrink-0 text-[14px] text-text-3">{suffix}</span>}
      </div>
      {error ? (
        <p id={`${fieldId}-error`} role="alert" className="mt-1.5 text-[13px] text-danger-text">
          {error}
        </p>
      ) : hint ? (
        <p id={`${fieldId}-hint`} className="mt-1.5 text-[13px] text-text-3">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

interface NumberInputProps {
  value: number | null
  onChange: (value: number | null) => void
  decimals?: number
  min?: number
  max?: number
  className?: string
  ariaLabel: string
  placeholder?: string
  autoFocus?: boolean
  id?: string
}

/**
 * Campo numérico con teclado decimal. Guarda el texto tal cual mientras se escribe
 * ("72," es válido a medias) y solo emite números.
 */
export function NumberInput({ value, onChange, decimals = 1, min, max, className, ariaLabel, placeholder, autoFocus, id }: NumberInputProps) {
  const [text, setText] = useState(value === null ? '' : fmtSmart(value, decimals).replace(/\./g, ''))
  const [focused, setFocused] = useState(false)

  useEffect(() => {
    if (!focused) setText(value === null ? '' : fmtSmart(value, decimals).replace(/\./g, ''))
  }, [value, decimals, focused])

  return (
    <input
      id={id}
      type="text"
      inputMode={decimals > 0 ? 'decimal' : 'numeric'}
      autoComplete="off"
      enterKeyHint="done"
      aria-label={ariaLabel}
      placeholder={placeholder}
      autoFocus={autoFocus}
      value={text}
      onFocus={(event) => {
        setFocused(true)
        event.currentTarget.select()
      }}
      onBlur={() => {
        setFocused(false)
        if (value !== null) {
          const clamped = Math.min(max ?? Infinity, Math.max(min ?? -Infinity, value))
          if (clamped !== value) onChange(clamped)
        }
      }}
      onChange={(event) => {
        const raw = event.target.value.replace(/[^\d.,]/g, '')
        setText(raw)
        const parsed = parseNumber(raw)
        onChange(Number.isFinite(parsed) ? parsed : null)
      }}
      data-num
      className={clsx('bg-transparent outline-none placeholder:text-text-3', className)}
    />
  )
}

interface StepperProps {
  value: number
  onChange: (value: number) => void
  step?: number
  min?: number
  max?: number
  decimals?: number
  unit?: string
  label: string
}

export function Stepper({ value, onChange, step = 1, min = 0, max = 9999, decimals = 0, unit, label }: StepperProps) {
  const set = (next: number) => {
    const clamped = Math.min(max, Math.max(min, Number(next.toFixed(decimals))))
    if (clamped !== value) {
      haptic('select')
      onChange(clamped)
    }
  }
  const button = 'grid size-12 place-items-center rounded-full bg-surface-2 border border-border text-text active:scale-90 transition-transform disabled:opacity-35'
  return (
    <div className="flex items-center justify-between gap-3" role="group" aria-label={label}>
      <button type="button" className={button} onClick={() => set(value - step)} disabled={value <= min} aria-label={`Reducir ${label.toLowerCase()}`}>
        <Minus className="size-5" aria-hidden />
      </button>
      <div className="flex min-w-0 flex-1 items-baseline justify-center gap-1.5">
        <NumberInput
          value={value}
          onChange={(v) => v !== null && onChange(v)}
          decimals={decimals}
          min={min}
          max={max}
          ariaLabel={label}
          className="w-[4.2ch] min-w-0 text-center text-[44px] leading-none font-semibold tracking-[-0.03em] text-text"
        />
        {unit && <span className="text-[17px] font-medium text-text-3">{unit}</span>}
      </div>
      <button type="button" className={button} onClick={() => set(value + step)} disabled={value >= max} aria-label={`Aumentar ${label.toLowerCase()}`}>
        <Plus className="size-5" aria-hidden />
      </button>
    </div>
  )
}

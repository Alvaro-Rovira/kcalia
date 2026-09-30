import { animate, useReducedMotion } from 'motion/react'
import { useEffect, useRef } from 'react'
import { fmt } from '@/lib/format'

interface Props {
  value: number
  decimals?: number
  /** Valor desde el que arranca la primera animación. */
  from?: number
  duration?: number
  className?: string
  format?: (value: number) => string
}

/** Número con efecto contador. Escribe en el DOM directamente: no re-renderiza por fotograma. */
export function AnimatedNumber({ value, decimals = 0, from = 0, duration = 0.9, className, format }: Props) {
  const ref = useRef<HTMLSpanElement>(null)
  const shown = useRef(from)
  const reduce = useReducedMotion()
  const render = format ?? ((n: number) => fmt(n, decimals))

  useEffect(() => {
    const node = ref.current
    if (!node) return
    if (reduce || shown.current === value) {
      shown.current = value
      node.textContent = render(value)
      return
    }
    const controls = animate(shown.current, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => {
        shown.current = latest
        node.textContent = render(latest)
      },
    })
    return () => controls.stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, reduce, duration, decimals])

  return (
    <span ref={ref} data-num className={className}>
      {render(reduce ? value : shown.current)}
    </span>
  )
}

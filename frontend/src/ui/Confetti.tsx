import { useEffect, useRef } from 'react'

interface Piece {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  rotation: number
  spin: number
  color: string
  life: number
}

function readColors(): string[] {
  const style = getComputedStyle(document.documentElement)
  return ['--kcal', '--protein', '--carbs', '--fat', '--kcal-from'].map((name) => style.getPropertyValue(name).trim())
}

/** Confeti ligero sobre canvas: una ráfaga corta desde `origin` y desaparece solo. */
export function Confetti({ run, originY = 0.32 }: { run: number; originY?: number }) {
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const node = canvas.current
    if (!run || !node) return
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const context = node.getContext('2d')
    if (!context) return
    const ratio = Math.min(2, window.devicePixelRatio || 1)
    const width = window.innerWidth
    const height = window.innerHeight
    node.width = width * ratio
    node.height = height * ratio
    context.scale(ratio, ratio)
    const colors = readColors()
    const pieces: Piece[] = Array.from({ length: 70 }, () => {
      const angle = -Math.PI / 2 + (Math.random() - 0.5) * 2.1
      const speed = 5 + Math.random() * 8
      return {
        x: width / 2,
        y: height * originY,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        size: 5 + Math.random() * 5,
        rotation: Math.random() * Math.PI,
        spin: (Math.random() - 0.5) * 0.4,
        color: colors[Math.floor(Math.random() * colors.length)],
        life: 1,
      }
    })
    let frame = 0
    const tick = () => {
      context.clearRect(0, 0, width, height)
      let alive = false
      for (const p of pieces) {
        p.vy += 0.28
        p.vx *= 0.985
        p.x += p.vx
        p.y += p.vy
        p.rotation += p.spin
        p.life -= 0.011
        if (p.life <= 0 || p.y > height + 20) continue
        alive = true
        context.save()
        context.globalAlpha = Math.min(1, p.life * 1.6)
        context.translate(p.x, p.y)
        context.rotate(p.rotation)
        context.fillStyle = p.color
        context.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2)
        context.restore()
      }
      if (alive) frame = requestAnimationFrame(tick)
      else context.clearRect(0, 0, width, height)
    }
    frame = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(frame)
      context.setTransform(1, 0, 0, 1, 0, 0)
      context.clearRect(0, 0, node.width, node.height)
    }
  }, [run, originY])

  return <canvas ref={canvas} aria-hidden className="pointer-events-none fixed inset-0 z-[60] size-full" />
}

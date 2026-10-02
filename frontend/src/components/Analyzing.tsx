import { AnimatePresence, motion } from 'motion/react'
import { Mic, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { GRAM_MACROS } from '@/lib/macros'

export type AnalyzeMode = 'text' | 'photo' | 'voice' | 'label'

const MESSAGES: Record<AnalyzeMode, string[]> = {
  text: ['Buscando en tu historial…', 'Consultando a la IA…', 'Pesando los ingredientes…', 'Sumando los macros…'],
  photo: ['Mirando tu plato…', 'Identificando los alimentos…', 'Estimando las cantidades…', 'Sumando los macros…'],
  voice: ['Escuchando tu audio…', 'Pasándolo a texto…'],
  label: ['Leyendo la etiqueta…', 'Buscando las calorías…', 'Anotando los macros…', 'Comprobando que cuadran…'],
}

/** Animación de espera mientras la IA trabaja: anillo girando o, si hay foto, un barrido sobre ella. */
export function Analyzing({ mode, preview }: { mode: AnalyzeMode; preview?: string }) {
  const messages = MESSAGES[mode]
  const [index, setIndex] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setIndex((i) => Math.min(i + 1, messages.length - 1)), 1500)
    return () => clearInterval(timer)
  }, [messages.length])

  return (
    <div role="status" aria-live="polite" className="flex flex-col items-center py-10">
      <div className="relative grid size-[132px] place-items-center">
        {preview ? (
          <div className="relative size-[132px] overflow-hidden rounded-xl border border-border">
            <img src={preview} alt="" className="size-full object-cover" />
            <motion.div
              className="absolute inset-x-0 h-10 bg-gradient-to-b from-transparent via-accent/40 to-transparent"
              animate={{ top: ['-30%', '100%'] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
            />
          </div>
        ) : (
          <>
            <motion.div
              className="absolute inset-0 rounded-full"
              style={{ background: 'conic-gradient(from 0deg, transparent 0 55%, var(--kcal-from), var(--kcal))', mask: 'radial-gradient(farthest-side, transparent calc(100% - 7px), #000 calc(100% - 6px))', WebkitMask: 'radial-gradient(farthest-side, transparent calc(100% - 7px), #000 calc(100% - 6px))' }}
              animate={{ rotate: 360 }}
              transition={{ duration: 1.3, repeat: Infinity, ease: 'linear' }}
            />
            {GRAM_MACROS.map((m, i) => (
              <motion.div
                key={m.key}
                className="absolute"
                style={{ inset: 20 + i * 11 }}
                animate={{ rotate: i % 2 ? -360 : 360 }}
                transition={{ duration: 2.2 + i * 0.7, repeat: Infinity, ease: 'linear' }}
              >
                <span className="absolute -top-1 left-1/2 size-2 -translate-x-1/2 rounded-full" style={{ background: m.color }} />
              </motion.div>
            ))}
            <motion.div animate={{ scale: [1, 1.12, 1] }} transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}>
              {mode === 'voice' ? <Mic className="size-8 text-accent-text" aria-hidden /> : <Sparkles className="size-8 text-accent-text" aria-hidden />}
            </motion.div>
          </>
        )}
      </div>
      <div className="mt-6 h-6 overflow-hidden">
        <AnimatePresence mode="wait" initial={false}>
          <motion.p
            key={index}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.22 }}
            className="text-[15.5px] font-medium text-text"
          >
            {messages[index]}
          </motion.p>
        </AnimatePresence>
      </div>
    </div>
  )
}

import { Copy } from 'lucide-react'
import { haptic } from '@/lib/haptics'
import { voiceShortcutUrl } from '@/lib/shortcuts'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { Sheet } from '@/ui/Sheet'
import { toast } from '@/ui/toast'

const STEPS: { title: string; text: string }[] = [
  { title: 'Crea el atajo', text: 'Abre la app Atajos, pulsa «+» y llámalo «Apuntar en Kcalia». Ese nombre es lo que le dirás a Siri.' },
  { title: 'Dictar texto', text: 'Añade la acción «Dictar texto», con el idioma en español.' },
  { title: 'Codificar URL', text: 'Añade «Codificar URL» (en algunas versiones, «Codificar o descodificar URL») sobre el texto dictado.' },
  { title: 'URL', text: 'Añade la acción «URL», pega la dirección de abajo y, justo detrás, inserta la variable con el texto codificado.' },
  { title: 'Abrir URLs', text: 'Añade «Abrir URLs» y guarda el atajo.' },
  { title: 'Úsalo', text: 'Di «Oye Siri, apuntar en Kcalia», cuenta qué has comido y revisa el texto antes de pulsar «Analizar».' },
]

export function VoiceShortcutSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const url = voiceShortcutUrl(window.location.origin)

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      haptic('success')
      toast.success('Dirección copiada', 'Pégala en la acción «URL» del atajo.')
    } catch {
      toast.error('No se ha podido copiar', 'Mantén pulsada la dirección para copiarla a mano.')
    }
  }

  return (
    <Sheet open={open} onClose={onClose} title="Atajo de voz en iPhone" tall>
      <div className="space-y-4 pt-1">
        <p className="text-[14px] leading-relaxed text-text-2">Apunta una comida hablando con Siri, sin abrir antes la app. Se configura una vez en la app Atajos.</p>
        <ol className="space-y-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-3">
              <span className="grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-[13px] font-semibold text-accent-text" data-num>
                {index + 1}
              </span>
              <span className="min-w-0 pt-0.5 text-[14.5px] leading-relaxed text-text-2">
                <strong className="font-semibold text-text">{step.title}.</strong> {step.text}
              </span>
            </li>
          ))}
        </ol>
        <div className="rounded-lg border border-border bg-surface-2 p-3">
          <p className="text-[12.5px] font-medium text-text-3">Dirección para la acción «URL»</p>
          <p className="mt-1 font-mono text-[13.5px] break-all text-text select-all" data-testid="voice-url">
            {url}
          </p>
          <Button variant="secondary" size="sm" className="mt-2.5" onClick={() => void copy()}>
            <Copy className="size-4" aria-hidden />
            Copiar dirección
          </Button>
        </div>
        <Notice level="info">
          El iPhone abre estos enlaces en Safari, no en la app de la pantalla de inicio: la primera vez tendrás que iniciar sesión también en Safari. Kcalia nunca
          analiza nada solo al abrir el enlace, así que no gasta IA sin que pulses «Analizar».
        </Notice>
      </div>
    </Sheet>
  )
}

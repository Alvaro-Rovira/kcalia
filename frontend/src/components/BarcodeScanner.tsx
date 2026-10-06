import { CameraOff, Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { normalizeBarcode } from '@/lib/barcode'
import { haptic } from '@/lib/haptics'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'

type Detect = (video: HTMLVideoElement) => Promise<string | null>
type Status = 'starting' | 'scanning' | 'denied' | 'unavailable'

interface NativeDetector {
  detect: (source: CanvasImageSource) => Promise<{ rawValue: string }[]>
}
interface NativeDetectorClass {
  new (options: { formats: string[] }): NativeDetector
  getSupportedFormats: () => Promise<string[]>
}

/**
 * Lector de códigos: el BarcodeDetector del navegador si existe (Chrome en Android) y, si no (Safari en iPhone),
 * zxing-wasm, que solo se descarga en ese momento y desde este mismo servidor.
 */
async function createDetector(): Promise<Detect> {
  const Native = (window as unknown as { BarcodeDetector?: NativeDetectorClass }).BarcodeDetector
  if (Native) {
    try {
      const supported = await Native.getSupportedFormats()
      const formats = ['ean_13', 'ean_8', 'upc_a', 'upc_e'].filter((f) => supported.includes(f))
      if (formats.length) {
        const detector = new Native({ formats })
        return async (video) => (await detector.detect(video))[0]?.rawValue ?? null
      }
    } catch {
      // Se cae al lector de respaldo.
    }
  }
  const [{ prepareZXingModule, readBarcodes }, { default: wasmUrl }] = await Promise.all([
    import('zxing-wasm/reader'),
    import('zxing-wasm/reader/zxing_reader.wasm?url'),
  ])
  // Sin esto, la librería descargaría el .wasm de un CDN externo (y la CSP lo bloquearía).
  prepareZXingModule({ overrides: { locateFile: (path: string, prefix: string) => (path.endsWith('.wasm') ? wasmUrl : prefix + path) } })
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d', { willReadFrequently: true })
  return async (video) => {
    const width = video.videoWidth
    const height = video.videoHeight
    if (!width || !height || !context) return null
    // Solo la franja central, donde está el recuadro: menos píxeles, lectura más rápida.
    const w = Math.round(width * 0.86)
    const h = Math.round(height * 0.5)
    canvas.width = w
    canvas.height = h
    context.drawImage(video, (width - w) / 2, (height - h) / 2, w, h, 0, 0, w, h)
    const results = await readBarcodes(context.getImageData(0, 0, w, h), {
      formats: ['EAN13', 'EAN8', 'UPCA', 'UPCE'],
      tryHarder: true,
      maxNumberOfSymbols: 1,
    })
    return results.find((r) => r.isValid)?.text ?? null
  }
}

interface Props {
  onDetected: (code: string) => void
  onCancel: () => void
}

/** Cámara trasera con un recuadro; al leer el mismo código dos veces seguidas, lo da por bueno. */
export default function BarcodeScanner({ onDetected, onCancel }: Props) {
  const video = useRef<HTMLVideoElement>(null)
  const [status, setStatus] = useState<Status>('starting')
  const [manual, setManual] = useState('')
  const [manualError, setManualError] = useState('')
  const detected = useRef(onDetected)
  detected.current = onDetected

  useEffect(() => {
    let stream: MediaStream | null = null
    let stopped = false
    let timer: number | undefined
    let last = ''
    let hits = 0

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) return setStatus('unavailable')
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        })
      } catch (error) {
        setStatus(error instanceof DOMException && error.name === 'NotAllowedError' ? 'denied' : 'unavailable')
        return
      }
      const element = video.current
      if (stopped || !element) {
        stream.getTracks().forEach((t) => t.stop())
        return
      }
      element.srcObject = stream
      await element.play().catch(() => undefined)
      let detect: Detect
      try {
        detect = await createDetector()
      } catch {
        setStatus('unavailable')
        return
      }
      setStatus('scanning')
      const tick = async () => {
        if (stopped) return
        try {
          const code = normalizeBarcode((await detect(element)) ?? '')
          if (code) {
            hits = code === last ? hits + 1 : 1
            last = code
            if (hits >= 2) {
              stopped = true
              haptic('success')
              detected.current(code)
              return
            }
          }
        } catch {
          // Un fotograma que no se puede leer no detiene el escáner.
        }
        timer = window.setTimeout(() => void tick(), 160)
      }
      void tick()
    }

    void start()
    return () => {
      stopped = true
      window.clearTimeout(timer)
      stream?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  function submitManual() {
    const code = normalizeBarcode(manual)
    if (!code) {
      haptic('error')
      return setManualError('Revisa los números: un código de producto tiene 8 o 13 cifras.')
    }
    onDetected(code)
  }

  const cameraProblem = status === 'denied' || status === 'unavailable'

  return (
    <div className="space-y-4 pt-1">
      {cameraProblem ? (
        <div className="grid aspect-[4/3] place-items-center rounded-lg border border-border bg-surface-2 p-6 text-center">
          <div>
            <CameraOff className="mx-auto size-8 text-text-3" aria-hidden />
            <p className="mt-3 text-[14.5px] leading-relaxed text-text-2">
              {status === 'denied'
                ? 'No tengo permiso para usar la cámara. Actívalo en los ajustes del navegador o escribe el código.'
                : 'No hay cámara disponible. Escribe los números del código de barras.'}
            </p>
          </div>
        </div>
      ) : (
        <div className="relative aspect-[4/3] overflow-hidden rounded-lg bg-bg">
          <video ref={video} playsInline muted className="size-full object-cover" aria-label="Vista de la cámara" />
          {/* Recuadro guía: el código, horizontal y dentro. */}
          <div aria-hidden className="pointer-events-none absolute inset-x-[7%] top-1/4 bottom-1/4 rounded-md border-2 border-accent shadow-[0_0_0_999px_var(--scrim)]">
            <div className="absolute inset-x-3 top-1/2 h-0.5 -translate-y-1/2 animate-pulse-soft rounded-full bg-accent" />
          </div>
          <p role="status" className="absolute inset-x-0 bottom-3 text-center text-[13.5px] font-medium text-text">
            {status === 'starting' ? 'Abriendo la cámara…' : 'Apunta al código de barras del envase'}
          </p>
        </div>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault()
          submitManual()
        }}
        className="flex items-end gap-2"
      >
        <label className="block min-w-0 flex-1">
          <span className="mb-1 block text-[13px] font-medium text-text-2">O escribe el código</span>
          <input
            value={manual}
            onChange={(event) => {
              setManual(event.target.value)
              setManualError('')
            }}
            inputMode="numeric"
            autoComplete="off"
            maxLength={20}
            placeholder="8410000000000"
            aria-label="Código de barras"
            className="h-12 w-full rounded-sm border border-border bg-surface-2 px-3.5 text-text outline-none placeholder:text-text-3 focus:border-accent"
            data-num
          />
        </label>
        <Button type="submit" size="sm" className="!h-12" icon={<Search className="size-4" aria-hidden />}>
          Buscar
        </Button>
      </form>
      {manualError && <Notice level="warn">{manualError}</Notice>}
      <Button variant="ghost" block onClick={onCancel}>
        Volver
      </Button>
    </div>
  )
}

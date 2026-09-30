import { useCallback, useEffect, useRef, useState } from 'react'

const MAX_SECONDS = 60
const MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']

export interface Recording {
  blob: Blob
  filename: string
}

export type RecorderError = 'unsupported' | 'denied' | 'failed'

function pickMime(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined
  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type))
}

const extension = (mime: string) => (mime.includes('mp4') ? 'm4a' : mime.includes('ogg') ? 'ogg' : 'webm')

/** Grabación de voz con MediaRecorder y nivel de entrada en vivo para animar la onda. */
export function useRecorder(onDone: (recording: Recording) => void, onError: (error: RecorderError) => void) {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [level, setLevel] = useState(0)
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const audio = useRef<AudioContext | null>(null)
  const frame = useRef(0)
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined)
  const cancelled = useRef(false)
  const handlers = useRef({ onDone, onError })
  handlers.current = { onDone, onError }

  const cleanup = useCallback(() => {
    cancelAnimationFrame(frame.current)
    clearInterval(timer.current)
    stream.current?.getTracks().forEach((track) => track.stop())
    stream.current = null
    void audio.current?.close().catch(() => undefined)
    audio.current = null
    recorder.current = null
    setRecording(false)
    setLevel(0)
  }, [])

  const stop = useCallback((discard = false) => {
    cancelled.current = discard
    if (recorder.current && recorder.current.state !== 'inactive') recorder.current.stop()
    else cleanup()
  }, [cleanup])

  const start = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      handlers.current.onError('unsupported')
      return
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      })
      stream.current = media
      const mime = pickMime()
      const instance = new MediaRecorder(media, mime ? { mimeType: mime, audioBitsPerSecond: 32_000 } : undefined)
      recorder.current = instance
      cancelled.current = false
      const chunks: Blob[] = []
      instance.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data)
      }
      instance.onstop = () => {
        const type = instance.mimeType || mime || 'audio/webm'
        const blob = new Blob(chunks, { type })
        const discard = cancelled.current
        cleanup()
        if (!discard) handlers.current.onDone({ blob, filename: `audio.${extension(type)}` })
      }
      instance.onerror = () => {
        cleanup()
        handlers.current.onError('failed')
      }
      instance.start()
      setSeconds(0)
      setRecording(true)
      timer.current = setInterval(() => {
        setSeconds((s) => {
          if (s + 1 >= MAX_SECONDS) stop()
          return s + 1
        })
      }, 1000)

      // Nivel de entrada (RMS) para que la onda responda a la voz.
      const context = new AudioContext()
      audio.current = context
      const analyser = context.createAnalyser()
      analyser.fftSize = 256
      context.createMediaStreamSource(media).connect(analyser)
      const data = new Uint8Array(analyser.fftSize)
      const tick = () => {
        analyser.getByteTimeDomainData(data)
        let sum = 0
        for (const value of data) sum += ((value - 128) / 128) ** 2
        setLevel(Math.min(1, Math.sqrt(sum / data.length) * 4))
        frame.current = requestAnimationFrame(tick)
      }
      tick()
    } catch (error) {
      cleanup()
      const name = error instanceof DOMException ? error.name : ''
      handlers.current.onError(name === 'NotAllowedError' || name === 'SecurityError' ? 'denied' : 'failed')
    }
  }, [cleanup, stop])

  useEffect(() => () => stop(true), [stop])

  return { recording, seconds, level, start, stop, maxSeconds: MAX_SECONDS }
}

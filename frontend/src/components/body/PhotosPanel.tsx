import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Camera, Columns2, ImagePlus, Lock, Trash2, WifiOff } from 'lucide-react'
import { useRef, useState } from 'react'
import { useOnline, usePhotos, useWeights } from '@/hooks/data'
import { api, errorMessage, newClientId } from '@/lib/api'
import { diffDays, fmtMedium, todayISO } from '@/lib/dates'
import { capitalize, fmt, fmtSigned, plural } from '@/lib/format'
import { haptic } from '@/lib/haptics'
import { downscaleImage } from '@/lib/image'
import type { ProgressPhoto } from '@/lib/types'
import { keys } from '@/offline/queryClient'
import { Button } from '@/ui/Button'
import { EmptyState } from '@/ui/EmptyState'
import { Notice } from '@/ui/Notice'
import { Sheet } from '@/ui/Sheet'
import { Skeleton } from '@/ui/Skeleton'
import { toast } from '@/ui/toast'

const src = (photo: ProgressPhoto) => `/api/photos/${photo.id}/image`

/** Fotos de progreso: se reducen en el móvil antes de subirlas y se comparan dos fechas lado a lado. */
export function PhotosPanel() {
  const client = useQueryClient()
  const online = useOnline()
  const photos = usePhotos()
  const weights = useWeights()
  const camera = useRef<HTMLInputElement>(null)
  const gallery = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [selecting, setSelecting] = useState(false)
  const [selected, setSelected] = useState<number[]>([])
  const [shown, setShown] = useState<ProgressPhoto[] | null>(null)
  const list = photos.data ?? []

  async function upload(file: File | undefined) {
    if (!file) return
    if (!navigator.onLine) return toast.error('Sin conexión', 'Las fotos se suben cuando hay red.')
    setUploading(true)
    try {
      const image = await downscaleImage(file, 1280, 0.8)
      const form = new FormData()
      form.append('image', image, 'progreso.jpg')
      form.append('date', todayISO())
      form.append('client_id', newClientId())
      await api.post('/api/photos', form)
      await client.invalidateQueries({ queryKey: keys.photos })
      haptic('success')
      toast.success('Foto guardada', 'Solo la ves tú.')
    } catch (error) {
      toast.error('No se ha podido subir la foto', errorMessage(error))
    } finally {
      setUploading(false)
    }
  }

  async function remove(photo: ProgressPhoto) {
    try {
      await api.delete(`/api/photos/${photo.id}`)
      client.setQueryData<{ photos: ProgressPhoto[] }>(keys.photos, (old) => (old ? { photos: old.photos.filter((p) => p.id !== photo.id) } : old))
      haptic('warning')
      toast({ title: 'Foto borrada', description: capitalize(fmtMedium(photo.date)) })
      setShown(null)
    } catch (error) {
      toast.error('No se ha podido borrar', errorMessage(error))
    }
  }

  function tap(photo: ProgressPhoto) {
    if (!selecting) return setShown([photo])
    haptic('select')
    const next = selected.includes(photo.id) ? selected.filter((id) => id !== photo.id) : [...selected, photo.id].slice(-2)
    setSelected(next)
    if (next.length === 2) {
      const pair = list.filter((p) => next.includes(p.id)).sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id)
      setShown(pair)
      setSelecting(false)
      setSelected([])
    }
  }

  // Peso de cada foto (la pesada más cercana anterior o del mismo día), para dar contexto a la comparación.
  const weightOn = (date: string) => {
    const entries = weights.data?.entries ?? []
    const before = entries.filter((e) => e.date <= date)
    return before.length ? before[before.length - 1].avg : null
  }

  return (
    <div className="mt-4 space-y-4">
      <input ref={camera} type="file" accept="image/*" capture="user" className="hidden" tabIndex={-1} aria-hidden onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = '' }} />
      <input ref={gallery} type="file" accept="image/*" className="hidden" tabIndex={-1} aria-hidden onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = '' }} />

      <div className="grid grid-cols-2 gap-2.5">
        <Button disabled={!online} loading={uploading} onClick={() => camera.current?.click()} icon={<Camera className="size-5" aria-hidden />}>
          Hacer foto
        </Button>
        <Button variant="secondary" disabled={!online || uploading} onClick={() => gallery.current?.click()} icon={<ImagePlus className="size-5" aria-hidden />}>
          De la galería
        </Button>
      </div>
      {!online && (
        <Notice level="info">
          <span className="flex items-center gap-2">
            <WifiOff className="size-4 shrink-0" aria-hidden /> Las fotos se suben y se cargan con conexión.
          </span>
        </Notice>
      )}
      <p className="flex items-start gap-2 text-[13px] leading-snug text-text-3">
        <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        Se reducen en el móvil y se guardan en tu servidor. No entran en la exportación de datos.
      </p>

      {photos.isPending ? (
        <Skeleton className="h-48 !rounded-[22px]" />
      ) : list.length === 0 ? (
        <div className="card">
          <EmptyState art="scale" title="Sin fotos todavía" text="Una foto cada pocas semanas, con la misma luz y la misma postura, dice más que muchos números." compact />
        </div>
      ) : (
        <section aria-label="Fotos de progreso">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[14px] text-text-2" data-num>
              {list.length} {plural(list.length, 'foto', 'fotos')}
            </p>
            {list.length >= 2 && (
              <Button
                variant={selecting ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => {
                  setSelecting((v) => !v)
                  setSelected([])
                }}
                icon={<Columns2 className="size-4" aria-hidden />}
              >
                {selecting ? 'Elige dos fotos' : 'Comparar'}
              </Button>
            )}
          </div>
          <ul className="mt-2.5 grid grid-cols-3 gap-2">
            {list.map((photo) => (
              <li key={photo.id}>
                <button
                  type="button"
                  onClick={() => tap(photo)}
                  aria-pressed={selecting ? selected.includes(photo.id) : undefined}
                  aria-label={`Foto del ${fmtMedium(photo.date)}`}
                  className={clsx('relative block aspect-[3/4] w-full overflow-hidden rounded-md border-2 bg-surface-2', selected.includes(photo.id) ? 'border-accent' : 'border-transparent')}
                >
                  <img src={src(photo)} alt="" loading="lazy" className="size-full object-cover" />
                  <span className="absolute inset-x-0 bottom-0 bg-scrim px-1.5 py-1 text-[11.5px] font-medium text-text" data-num>
                    {fmtMedium(photo.date)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <Sheet open={!!shown} onClose={() => setShown(null)} title={shown && shown.length === 2 ? 'Comparación' : 'Foto de progreso'} tall>
        {shown && (
          <div className="space-y-4">
            <div className={clsx('grid gap-2', shown.length === 2 ? 'grid-cols-2' : 'grid-cols-1')}>
              {shown.map((photo) => {
                const kg = weightOn(photo.date)
                return (
                  <figure key={photo.id}>
                    <img src={src(photo)} alt={`Foto de progreso del ${fmtMedium(photo.date)}`} className="aspect-[3/4] w-full rounded-md bg-surface-2 object-cover" />
                    <figcaption className="mt-1.5 text-center text-[13px] text-text-2" data-num>
                      {capitalize(fmtMedium(photo.date))}
                      {kg !== null && <span className="block text-[12px] text-text-3">{fmt(kg, 1)} kg de media</span>}
                    </figcaption>
                  </figure>
                )
              })}
            </div>
            {shown.length === 2 && (
              <p className="text-center text-[14px] text-text-2" data-num>
                {Math.abs(diffDays(shown[1].date, shown[0].date))} días entre una y otra
                {weightOn(shown[0].date) !== null && weightOn(shown[1].date) !== null && (
                  <> · {fmtSigned((weightOn(shown[1].date) ?? 0) - (weightOn(shown[0].date) ?? 0), 1)} kg</>
                )}
              </p>
            )}
            {shown.length === 1 && (
              <Button variant="danger" size="sm" onClick={() => void remove(shown[0])} icon={<Trash2 className="size-4" aria-hidden />}>
                Borrar esta foto
              </Button>
            )}
          </div>
        )}
      </Sheet>
    </div>
  )
}

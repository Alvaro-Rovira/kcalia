import { Logo } from './Logo'

/** Pantalla de arranque: el isotipo latiendo mientras llega la primera respuesta. */
export function Splash() {
  return (
    <div role="status" aria-label="Cargando Kcalia" className="grid min-h-dvh place-items-center">
      <div className="animate-pulse-soft">
        <Logo size={72} />
      </div>
    </div>
  )
}

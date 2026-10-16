import { Component, type ErrorInfo, type ReactNode } from 'react'
import { clearLocalData } from '@/offline/queryClient'

/**
 * Si algo falla al dibujar, en lugar de dejar la pantalla en blanco (React desmonta todo) se ofrece reintentar o
 * borrar la copia de este dispositivo. Esto último importa: si la copia guardada no encaja con la app, fallaría igual
 * en cada arranque. Los cambios pendientes de enviar están en otra cola y se conservan.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Fallo al mostrar la pantalla', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <main role="alert" className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center gap-4 px-6 text-center">
        <h1 className="text-[22px] font-semibold tracking-[-0.02em] text-text">Algo ha fallado al mostrar esta pantalla</h1>
        <p className="text-[14.5px] leading-relaxed text-text-2">
          Tus datos están a salvo en el servidor, y los cambios que aún no se habían enviado se conservan.
        </p>
        <button
          type="button"
          onClick={() => this.setState({ error: null })}
          className="h-12 rounded-full bg-accent px-5 text-[15px] font-semibold text-on-accent"
        >
          Reintentar
        </button>
        <button
          type="button"
          onClick={() => void clearLocalData().finally(() => window.location.reload())}
          className="h-12 rounded-full border border-border px-5 text-[14.5px] font-medium text-text"
        >
          Borrar la copia de este dispositivo y recargar
        </button>
        <p className="text-[12px] break-words text-text-3">{error.message}</p>
      </main>
    )
  }
}

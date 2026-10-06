export class ApiError extends Error {
  status: number
  code?: string

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }

  /** No hubo respuesta del servidor: sin red o servidor caído. */
  get offline(): boolean {
    return this.status === 0
  }
}

const FALLBACK: Record<number, string> = {
  401: 'Tu sesión ha caducado. Vuelve a entrar.',
  403: 'No tienes permiso para hacer eso.',
  404: 'No he encontrado lo que buscabas.',
  413: 'El archivo es demasiado grande.',
  429: 'Demasiadas peticiones seguidas. Espera un momento.',
  502: 'El servidor no responde ahora mismo. Inténtalo en un momento.',
  503: 'El servicio no está disponible ahora mismo. Inténtalo en un momento.',
  504: 'El servidor ha tardado demasiado. Inténtalo otra vez.',
}

export const UNAUTHORIZED_EVENT = 'kcalia:unauthorized'
/** La cuenta ha dejado de estar aprobada (pendiente o bloqueada) mientras se usaba la app. */
export const ACCOUNT_EVENT = 'kcalia:account'

async function parseError(response: Response): Promise<ApiError> {
  let message = FALLBACK[response.status] ?? 'Algo ha fallado. Inténtalo de nuevo en un momento.'
  let code: string | undefined
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string' && body.detail) message = body.detail
    if (typeof body?.code === 'string') code = body.code
  } catch {
    // Respuesta sin JSON (p. ej. un 502 del proxy): vale el mensaje genérico.
  }
  return new ApiError(message, response.status, code)
}

async function request<T>(method: string, url: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const isForm = body instanceof FormData
  let response: Response
  try {
    response = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers: body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : undefined,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('Sin conexión. Comprueba tu red e inténtalo de nuevo.', 0, 'offline')
  }
  if (!response.ok) {
    const error = await parseError(response)
    if (response.status === 401 && !url.startsWith('/api/auth/')) {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT, { detail: error.code }))
    }
    if (response.status === 403 && error.code?.startsWith('account_')) {
      window.dispatchEvent(new CustomEvent(ACCOUNT_EVENT, { detail: error.code }))
    }
    throw error
  }
  return (await response.json()) as T
}

export const api = {
  get: <T>(url: string, signal?: AbortSignal) => request<T>('GET', url, undefined, signal),
  post: <T>(url: string, body?: unknown, signal?: AbortSignal) => request<T>('POST', url, body ?? {}, signal),
  put: <T>(url: string, body?: unknown) => request<T>('PUT', url, body ?? {}),
  patch: <T>(url: string, body?: unknown) => request<T>('PATCH', url, body ?? {}),
  delete: <T>(url: string) => request<T>('DELETE', url),
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Algo ha fallado. Inténtalo de nuevo en un momento.'
}

export function newClientId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

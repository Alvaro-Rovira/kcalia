import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() }))
vi.mock('@/lib/api', async () => ({ ...(await vi.importActual<typeof import('@/lib/api')>('@/lib/api')), api }))
vi.mock('idb-keyval', () => ({ get: vi.fn(async () => undefined), set: vi.fn(async () => undefined), del: vi.fn(async () => undefined) }))

const settle = () => new Promise((resolve) => setTimeout(resolve, 0))
const water = (clientId: string) => ({ type: 'water.add', body: { client_id: clientId, date: '2026-10-16', ml: 250 } }) as const

async function freshOutbox() {
  vi.resetModules()
  const { outbox, enqueue } = await import('./outbox')
  const { ApiError } = await import('@/lib/api')
  const rejected: string[] = []
  outbox.init({ onSynced: () => undefined, onRejected: (_op, error) => rejected.push(String(error.status)) })
  return { outbox, enqueue, ApiError, rejected }
}

beforeEach(() => {
  vi.stubGlobal('window', { addEventListener: vi.fn() })
  vi.stubGlobal('document', { addEventListener: vi.fn(), visibilityState: 'visible' })
})
afterEach(() => {
  vi.unstubAllGlobals()
  Object.values(api).forEach((fn) => fn.mockReset())
})

describe('cola de cambios sin conexión', () => {
  it('lo que el servidor rechaza para siempre se descarta, avisa y deja pasar lo siguiente', async () => {
    const { outbox, enqueue, ApiError, rejected } = await freshOutbox()
    api.post.mockRejectedValueOnce(new ApiError('dato que no cuadra', 422)).mockResolvedValueOnce({})
    await enqueue(water('agua-0001'))
    await enqueue(water('agua-0002'))
    await settle()
    expect(rejected).toEqual(['422'])
    expect(api.post).toHaveBeenCalledTimes(2)
    expect(outbox.pendingCount()).toBe(0)
  })

  it.each([429, 408, 500, 503])('un %i es pasajero: el cambio se queda en cola para reintentarlo', async (status) => {
    const { outbox, enqueue, ApiError, rejected } = await freshOutbox()
    api.post.mockRejectedValue(new ApiError('espera', status))
    await enqueue(water('agua-0003'))
    await settle()
    expect(rejected).toEqual([])
    expect(outbox.pendingCount()).toBe(1)
  })
})

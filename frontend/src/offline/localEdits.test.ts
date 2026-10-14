import { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Bootstrap } from '@/lib/types'
import { fetchBootstrap, markLocalEdit } from './localEdits'
import { keys } from './queryClient'

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/lib/api', () => ({ api }))

const boot = (training_days: number[], extra: Partial<Bootstrap> = {}) =>
  ({ prefs: { training_days, day_types: true }, day_types: {}, water_goal_ml: 2000, dishes: [], ...extra }) as unknown as Bootstrap

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => (resolve = r))
  return { promise, resolve }
}

afterEach(() => api.get.mockReset())

describe('recarga de los datos de arranque frente a cambios hechos en el móvil', () => {
  it('una respuesta anterior a un cambio local no lo pisa', async () => {
    const client = new QueryClient()
    client.setQueryData(keys.bootstrap, boot([0, 1, 2]))
    const server = deferred<Bootstrap>()
    api.get.mockReturnValue(server.promise)

    const pending = fetchBootstrap(client)
    // Mientras la petición va de camino, se marca otro día (cambio optimista y a la cola).
    markLocalEdit()
    client.setQueryData<Bootstrap>(keys.bootstrap, (old) => ({ ...old!, prefs: { ...old!.prefs!, training_days: [0, 1, 2, 3] } }))
    server.resolve(boot([0, 1, 2], { water_goal_ml: 2500 }))

    const result = await pending
    expect(result.prefs?.training_days).toEqual([0, 1, 2, 3])
    expect(result.water_goal_ml).toBe(2000) // también lo que va con las preferencias
  })

  it('sin cambios locales durante la petición manda el servidor', async () => {
    const client = new QueryClient()
    client.setQueryData(keys.bootstrap, boot([0, 1, 2]))
    api.get.mockResolvedValue(boot([4, 5], { water_goal_ml: 2500 }))
    const result = await fetchBootstrap(client)
    expect(result.prefs?.training_days).toEqual([4, 5])
    expect(result.water_goal_ml).toBe(2500)
  })
})

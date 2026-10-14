import type { QueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Bootstrap } from '@/lib/types'
import { keys } from './queryClient'

/**
 * Las preferencias y el tipo de día se cambian en el móvil al momento y viajan por la cola offline. Tras cada envío se
 * recargan los datos de arranque; si esa respuesta salió del servidor antes de un cambio hecho mientras tanto, traería
 * el valor viejo y lo pisaría (y el siguiente toque partiría de él: «marcar varios días seguidos» perdía alguno).
 * Por eso cada cambio local suma una versión, y una respuesta que empezó antes conserva los campos locales: el cambio
 * sigue en la cola y, cuando llegue al servidor, la siguiente recarga ya lo traerá.
 */
let version = 0

export function markLocalEdit(): void {
  version += 1
}

export async function fetchBootstrap(client: QueryClient): Promise<Bootstrap> {
  const started = version
  const fresh = await api.get<Bootstrap>('/api/bootstrap')
  if (version === started) return fresh
  const local = client.getQueryData<Bootstrap>(keys.bootstrap)
  if (!local) return fresh
  return { ...fresh, prefs: local.prefs, water_goal_ml: local.water_goal_ml, day_types: local.day_types }
}

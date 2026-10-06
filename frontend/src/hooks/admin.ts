import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export interface UsageTotals {
  ai: number
  stt: number
  prompt_tokens: number
  completion_tokens: number
  cost: number
}

export interface AdminUser {
  id: number
  username: string
  status: 'pending' | 'approved' | 'suspended'
  is_admin: boolean
  created_at: string
  last_seen_at: string | null
  sessions: number
  limits: { ai: number; stt: number; ai_custom: number | null; stt_custom: number | null }
  today: UsageTotals
  month: UsageTotals
}

export interface AdminOverview {
  pending: number
  users: { total: number; approved: number; suspended: number }
  today: UsageTotals & { ai_limit: number; stt_limit: number }
  month: UsageTotals
  ai_paused: boolean
  signup: { state: 'first' | 'open' | 'closed' | 'full'; allowed_by_server: boolean; open: boolean; max_pending: number }
  defaults: { ai_user_daily_limit: number; stt_user_daily_limit: number; admin_ai_daily_limit: number }
  prices: { ai_input_per_million: number; ai_output_per_million: number; stt_per_call: number }
}

export interface AuditEntry {
  id: number
  admin: string
  action: string
  target: string
  details: Record<string, unknown>
  created_at: string
}

export const adminKeys = {
  overview: ['admin', 'overview'] as const,
  users: ['admin', 'users'] as const,
  audit: ['admin', 'audit'] as const,
}

/** Resumen del panel. Solo se pide si la cuenta es la del administrador (para el indicador de solicitudes). */
export function useAdminOverview(enabled: boolean) {
  return useQuery({
    queryKey: adminKeys.overview,
    queryFn: () => api.get<AdminOverview>('/api/admin/overview'),
    enabled,
    // Consulta barata y solo del admin: siempre fresca al montar, para que el indicador no se quede atrás.
    staleTime: 0,
    refetchInterval: enabled ? 120_000 : false,
  })
}

export function useAdminUsers() {
  return useQuery({ queryKey: adminKeys.users, queryFn: () => api.get<{ users: AdminUser[] }>('/api/admin/users'), select: (d) => d.users })
}

export function useAdminAudit() {
  return useQuery({ queryKey: adminKeys.audit, queryFn: () => api.get<{ entries: AuditEntry[] }>('/api/admin/audit?limit=40'), select: (d) => d.entries })
}

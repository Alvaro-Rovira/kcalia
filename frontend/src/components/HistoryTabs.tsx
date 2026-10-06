import clsx from 'clsx'
import { NavLink } from 'react-router'

/** Historial: lo comido (diario) y lo previsto (plan semanal con su lista de la compra). */
export function HistoryTabs() {
  return (
    <nav aria-label="Historial" className="mb-4 flex rounded-md border border-border bg-surface-2 p-1">
      {[
        { to: '/historial', label: 'Diario' },
        { to: '/plan', label: 'Plan' },
      ].map(({ to, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            clsx(
              'flex h-10 flex-1 items-center justify-center rounded-[11px] text-[14px] font-medium transition-colors',
              isActive ? 'border border-border bg-surface text-text shadow-sm' : 'text-text-3 hover:text-text-2',
            )
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

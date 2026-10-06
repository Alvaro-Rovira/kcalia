import clsx from 'clsx'
import { NavLink } from 'react-router'

/** Las dos vistas de «Progreso» en el móvil: el resumen semanal y el cuerpo (peso, medidas y fotos). */
export function ProgressTabs() {
  return (
    <nav aria-label="Progreso" className="mb-4 flex rounded-md border border-border bg-surface-2 p-1 lg:hidden">
      {[
        { to: '/resumen', label: 'Resumen' },
        { to: '/peso', label: 'Cuerpo' },
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

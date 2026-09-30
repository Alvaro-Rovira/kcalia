import { Link } from 'react-router'
import { EmptyState } from '@/ui/EmptyState'

export default function NotFound() {
  return (
    <main className="page grid min-h-[70dvh] place-items-center">
      <EmptyState
        art="lost"
        title="Aquí no hay nada"
        text="Esta página no existe o se ha movido. Tu diario sigue en su sitio."
        action={
          <Link
            to="/"
            className="inline-flex h-12 items-center rounded-md bg-accent px-5 text-[15px] font-semibold text-on-accent shadow-md"
          >
            Volver a hoy
          </Link>
        }
      />
    </main>
  )
}

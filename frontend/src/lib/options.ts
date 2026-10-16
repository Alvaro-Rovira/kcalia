import { Armchair, Bike, Dumbbell, Equal, Flame, Footprints, PersonStanding, Rocket, Scale, TrendingDown, type LucideIcon } from 'lucide-react'
import type { Activity, Goal } from './types'

export const ACTIVITIES: { value: Activity; label: string; text: string; factor: number; Icon: LucideIcon }[] = [
  { value: 'sedentario', label: 'Sedentario', text: 'Sentado casi todo el día y poco o nada de ejercicio', factor: 1.2, Icon: Armchair },
  { value: 'ligero', label: 'Ligero', text: 'Sentado casi todo el día y entrenas 2-4 días por semana', factor: 1.375, Icon: Footprints },
  { value: 'moderado', label: 'Moderado', text: 'Mucho rato de pie o andando (10.000 pasos o más) y entrenas', factor: 1.55, Icon: PersonStanding },
  { value: 'alto', label: 'Alto', text: 'Trabajo físico, o entreno intenso casi a diario y muchos pasos', factor: 1.725, Icon: Bike },
  { value: 'muy_alto', label: 'Muy alto', text: 'Trabajo físico duro y además entrenas, o doble sesión diaria', factor: 1.9, Icon: Dumbbell },
]

export const GOALS: { value: Goal; label: string; text: string; tag: string; Icon: LucideIcon }[] = [
  { value: 'definicion_ligera', label: 'Definición ligera', text: 'Perder grasa sin prisa y sin pasar hambre', tag: '−15 %', Icon: TrendingDown },
  { value: 'definicion_agresiva', label: 'Definición agresiva', text: 'Perder grasa rápido durante unas semanas', tag: '−25 %', Icon: Flame },
  { value: 'mantenimiento', label: 'Mantenimiento', text: 'Quedarte como estás, en equilibrio', tag: '0 %', Icon: Equal },
  { value: 'recomposicion', label: 'Recomposición', text: 'Perder grasa y ganar músculo a la vez', tag: '−2,5 %', Icon: Scale },
  { value: 'volumen', label: 'Volumen', text: 'Ganar músculo con un superávit controlado', tag: '+7,5 %', Icon: Rocket },
]

export const ACTIVITY_LABEL = Object.fromEntries(ACTIVITIES.map((a) => [a.value, a.label])) as Record<Activity, string>
export const GOAL_LABEL = Object.fromEntries(GOALS.map((g) => [g.value, g.label])) as Record<Goal, string>

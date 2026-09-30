import { Armchair, Bike, Dumbbell, Equal, Flame, Footprints, PersonStanding, Rocket, Scale, TrendingDown, type LucideIcon } from 'lucide-react'
import type { Activity, Goal } from './types'

export const ACTIVITIES: { value: Activity; label: string; text: string; factor: number; Icon: LucideIcon }[] = [
  { value: 'sedentario', label: 'Sedentario', text: 'Trabajo sentado y poco o nada de ejercicio', factor: 1.2, Icon: Armchair },
  { value: 'ligero', label: 'Ligero', text: 'Ejercicio suave 1-3 días por semana', factor: 1.375, Icon: Footprints },
  { value: 'moderado', label: 'Moderado', text: 'Entreno 3-5 días por semana', factor: 1.55, Icon: PersonStanding },
  { value: 'alto', label: 'Alto', text: 'Entreno intenso 6-7 días por semana', factor: 1.725, Icon: Bike },
  { value: 'muy_alto', label: 'Muy alto', text: 'Trabajo físico o doble sesión diaria', factor: 1.9, Icon: Dumbbell },
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

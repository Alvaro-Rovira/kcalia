export type Sex = 'hombre' | 'mujer'
export type Activity = 'sedentario' | 'ligero' | 'moderado' | 'alto' | 'muy_alto'
export type Goal = 'definicion_ligera' | 'definicion_agresiva' | 'volumen' | 'mantenimiento' | 'recomposicion'
export type Slot = 'desayuno' | 'comida' | 'merienda' | 'cena' | 'snack'
export type Source = 'ai' | 'exact' | 'fuzzy' | 'cache' | 'favorite' | 'recent' | 'manual' | 'photo'
export type Via = 'text' | 'voice' | 'photo' | 'tap'
export type MacroKey = 'kcal' | 'protein' | 'carbs' | 'fat'
export type ThemePref = 'dark' | 'light' | 'auto'

export interface Macros {
  kcal: number
  protein: number
  carbs: number
  fat: number
}

export interface Item extends Macros {
  name: string
  qty: number
  unit: string
  grams: number
}

export interface Draft extends Macros {
  name: string
  text: string
  items: Item[]
  confidence: number
  assumptions: string[]
  source: Source
  dish_id: number | null
  favorite?: boolean
  score?: number
  matched_text?: string
}

export interface Meal extends Macros {
  id: number
  client_id: string
  date: string
  slot: Slot
  name: string
  text: string
  items: Item[]
  servings: number
  source: Source
  confidence: number
  assumptions: string[]
  dish_id: number | null
  created_at: string
  /** Guardada en el móvil, pendiente de llegar al servidor. */
  pending?: boolean
}

export interface MealInput {
  client_id: string
  date: string
  slot: Slot
  name: string
  text: string
  items: Item[]
  servings: number
  source: Source
  via: Via
  confidence: number
  assumptions: string[]
  dish_id: number | null
}

export interface Dish extends Macros {
  id: number
  name: string
  text: string
  norm: string
  aliases: string[]
  items: Item[]
  confidence: number
  assumptions: string[]
  origin: string
  favorite: boolean
  use_count: number
  last_used_at: string
}

export interface Profile {
  sex: Sex
  age: number
  height_cm: number
  weight_kg: number
  activity: Activity
  goal: Goal
  target_weight_kg: number | null
  weight_unit: 'kg' | 'lb'
}

export type ProfileInput = Omit<Profile, 'weight_unit'>

export interface Targets extends Macros {
  bmr: number
  tdee: number
  custom: boolean
  basis_weight_kg: number
}

export interface Warning {
  code: string
  level: 'info' | 'warn' | 'danger'
  text: string
}

export interface Plan extends Macros {
  bmr: number
  tdee: number
  activity_factor: number
  adjustment_pct: number
  protein_gkg: number
  fat_gkg: number
  ref_weight_kg: number
  bmi: number
  weekly_kg: number
  weeks_to_target: number | null
  goal_label: string
  warnings: Warning[]
}

export interface Bootstrap {
  user: { username: string }
  profile: Profile | null
  targets: Targets | null
  plan: Plan | null
  dishes: Dish[]
  ai: { configured: boolean; model: string; used_today: number; limit: number }
  server_date: string
}

export interface AuthStatus {
  registered: boolean
  authenticated: boolean
  username: string | null
}

export type ResolveResult =
  | { status: 'exact' | 'cache' | 'ai'; draft: Draft }
  | { status: 'fuzzy'; candidates: Draft[] }
  | { status: 'clarify'; question: string }

export interface DayTotal extends Macros {
  date: string
  meals: number
}

export interface WeightPoint {
  date: string
  kg: number
  avg: number
}

export interface WeightData {
  entries: WeightPoint[]
  target_kg: number | null
  recalc: (Macros & { from_kg: number; to_kg: number }) | null
}

export type DayStatus = 'cumplido' | 'bajo' | 'pasado' | 'sin_registro'

export interface WeekDay extends Macros {
  date: string
  logged: boolean
  status: DayStatus
  balance: number
  protein_met: boolean
}

export interface Badge {
  key: string
  label: string
  tone: 'kcal' | 'protein' | 'carbs' | 'fat' | 'neutral'
}

export interface WeekSummary {
  week_start: string
  week_end: string
  complete: boolean
  days: WeekDay[]
  days_elapsed: number
  logged_days: number
  on_target_days: number
  deficit_days: number
  surplus_days: number
  over_target_days: number
  protein_days: number
  total_kcal: number
  avg_kcal: number
  avg_protein: number
  avg_carbs: number
  avg_fat: number
  balance_total: number
  adherence_pct: number
  projection: { weekly_kg: number; weeks_per_kg: number | null; direction: 'perdida' | 'ganancia' | 'estable' } | null
  best_day: { date: string; kcal: number; diff: number } | null
  worst_day: { date: string; kcal: number; diff: number } | null
  weight: { avg: number | null; previous_avg: number | null; change: number | null; entries: number }
  targets: Macros & { tdee: number }
  vs_previous: {
    avg_kcal: number
    avg_protein: number
    adherence_pct: number
    balance_total: number
    logged_days: number
  } | null
  badges: Badge[]
}

export interface AchievementInfo {
  key: string
  title: string
  text: string
  icon: string
  unlocked_at: string | null
}

export interface Stats {
  streak: { current: number; best: number; today_done: boolean }
  achievements: AchievementInfo[]
  new_achievements: string[]
  ai: {
    used_today: number
    limit: number
    saved_total: number
    saved: { saved_exact: number; saved_fuzzy: number; saved_cache: number; saved_quick: number }
    calls_total: number
  }
  counts: { meals: number; weights: number; days: number }
}

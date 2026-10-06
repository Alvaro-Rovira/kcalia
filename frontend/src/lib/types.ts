export type Sex = 'hombre' | 'mujer'
export type Activity = 'sedentario' | 'ligero' | 'moderado' | 'alto' | 'muy_alto'
export type Goal = 'definicion_ligera' | 'definicion_agresiva' | 'volumen' | 'mantenimiento' | 'recomposicion'
export type Slot = 'desayuno' | 'comida' | 'merienda' | 'cena' | 'snack'
export type Source = 'ai' | 'exact' | 'fuzzy' | 'cache' | 'favorite' | 'recent' | 'manual' | 'photo' | 'product' | 'drink' | 'sugerencia' | 'import'
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
  /** Si sale de la etiqueta de un producto guardado. */
  product_id?: number | null
  /** Añadido a mano: al guardar la comida se aprende en la caché de ingredientes. */
  manual?: boolean
  /** Fibra y gramos de alcohol (opcionales: lo antiguo no los trae y cuentan como 0). */
  fiber?: number | null
  alcohol?: number | null
}

/** Ingrediente de la caché: macros por 100 g y gramos por unidad habitual. */
export interface FoodEntry {
  name: string
  norm: string
  kcal100: number
  protein100: number
  carbs100: number
  fat100: number
  fiber100?: number | null
  alcohol100?: number | null
  unit_grams: Record<string, number>
}

/** Producto envasado con las cifras de su etiqueta (por 100 g o 100 ml). */
export interface Product {
  id: number
  name: string
  alias: string
  basis: 'g' | 'ml'
  kcal100: number
  protein100: number
  carbs100: number
  fat100: number
  fiber100: number | null
  sugars100: number | null
  salt100: number | null
  unit_label: string
  unit_grams: number | null
  has_image: boolean
  barcode?: string | null
  use_count: number
  last_used_at: string
  created_at: string
  slot_counts?: Partial<Record<Slot, number>>
}

/** Lo que la IA ha leído de la foto de una etiqueta: se revisa antes de guardar. */
export interface LabelDraft {
  name: string
  alias: string
  basis: 'g' | 'ml'
  kcal100: number | null
  protein100: number | null
  carbs100: number | null
  fat100: number | null
  fiber100: number | null
  sugars100: number | null
  salt100: number | null
  unit_label: string
  unit_grams: number | null
  confidence: number
  warnings: string[]
  missing: string[]
  /** Si el borrador viene de escanear un código de barras (Open Food Facts). */
  barcode?: string | null
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
  fiber?: number
  alcohol?: number
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
  /** Veces que se ha comido en cada momento del día (últimos meses). */
  slot_counts?: Partial<Record<Slot, number>>
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

/** Preferencias guardadas en el servidor (cada versión añade campos con valor por defecto). */
export type DayKind = 'entreno' | 'descanso'

export interface DayTargetsValues {
  kcal: number
  protein: number
  carbs: number
  fat: number
}

export interface Prefs {
  water_goal_ml: number | null
  day_types?: boolean
  /** 0 = lunes. */
  training_days?: number[]
  training_kcal_adjust?: number
  rest_kcal_adjust?: number
  training_targets?: DayTargetsValues | null
  rest_targets?: DayTargetsValues | null
  add_exercise_kcal?: boolean
  rest_seconds?: number
  reminders?: boolean
  meal_reminders?: MealReminder[]
  /** Hora del aviso para pesarse («08:30») o null si está apagado. */
  weigh_reminder?: string | null
  weigh_days?: number[]
  suggest_enabled?: boolean
  suggest_min_kcal?: number | null
  suggest_hour?: string
  suggest_hidden?: string[]
}

export interface MealReminder {
  slot: Slot
  time: string
  enabled: boolean
}

export interface WaterEntry {
  client_id: string
  ml: number
  created_at: string
  pending?: boolean
}

export interface WaterDay {
  date: string
  total_ml: number
  goal_ml: number
  entries: WaterEntry[]
}

export interface Bootstrap {
  user: { username: string; is_admin?: boolean }
  profile: Profile | null
  targets: Targets | null
  plan: Plan | null
  dishes: Dish[]
  products: Product[]
  /** Caché de ingredientes (las versiones anteriores no la traían). */
  foods?: FoodEntry[]
  prefs?: Prefs
  water_goal_ml?: number
  /** Días con el tipo cambiado a mano (fecha -> entreno o descanso). */
  day_types?: Record<string, DayKind>
  /** Calorías estimadas de los entrenos de cada día (recientes). */
  exercise_kcal?: Record<string, number>
  /** Mínimo de calorías restantes para sugerir algo (SUGGEST_MIN_KCAL del servidor). */
  suggest_min_kcal_default?: number
  ai: {
    configured: boolean
    model: string
    used_today: number
    limit: number
    paused?: boolean
    stt_used_today?: number
    stt_limit?: number
  }
  server_date: string
}

export type AccountStatus = 'pending' | 'approved' | 'suspended'
/** first: instalación sin cuentas · open: se pueden solicitar · closed: cerrado · full: demasiadas pendientes */
export type SignupState = 'first' | 'open' | 'closed' | 'full'

export interface AuthStatus {
  registered: boolean
  authenticated: boolean
  username: string | null
  /** Las versiones anteriores no lo traían: sin dato, la cuenta se da por aprobada. */
  status?: AccountStatus | null
  is_admin?: boolean
  signup?: SignupState
}

export type ResolveResult =
  | { status: 'exact' | 'cache' | 'ai' | 'product'; draft: Draft }
  | { status: 'fuzzy'; candidates: Draft[] }
  | { status: 'clarify'; question: string }

export interface DayTotal extends Macros {
  date: string
  meals: number
  fiber?: number
  alcohol?: number
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
  target_kcal?: number
  kind?: DayKind | null
  fiber?: number
  alcohol?: number
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
  avg_fiber?: number
  alcohol?: { grams: number; kcal: number; days: number; pct: number }
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
    saved: { saved_exact: number; saved_fuzzy: number; saved_cache: number; saved_quick: number; saved_product: number }
    calls_total: number
  }
  counts: { meals: number; weights: number; days: number }
}

export type MeasureKey = 'waist' | 'chest' | 'arm' | 'hip' | 'thigh'

/** Medidas de un día, en centímetros. */
export type Measurement = { date: string } & Record<MeasureKey, number | null>

export interface ProgressPhoto {
  id: number
  client_id: string
  date: string
  size: number
  created_at: string
}

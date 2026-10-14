# Precisión de calorías — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que las kcal salgan de datos oficiales y reglas fijas en todo lo que no es reconocer el alimento o estimar
una ración, y que el gasto diario se mida con los datos reales del usuario.

**Architecture:** tabla de alimentos en `backend/app/data/` (extractos literales de CIQUAL 2025 y USDA + nombres en
español y recetas), módulo `foodtable.py` que la carga y empareja, canalización única `refine.py` por la que pasan
todas las comidas (IA, foto, plan, sugerencias, sin IA), `expenditure.py` para el gasto real y kcal netas en
`workouts.py`. La interfaz muestra el origen de cada valor.

**Tech Stack:** FastAPI + SQLAlchemy + SQLite (migraciones propias con `PRAGMA user_version`), pytest; React + Vite +
TypeScript, vitest, Playwright (e2e); Docker en la VPS.

**Spec:** `docs/superpowers/specs/2026-10-14-precision-kcal-design.md`

## Global Constraints

- Ninguna cifra de CIQUAL/USDA se altera: los extractos son literales y el código solo convierte «,» a «.», «-»,
  «traces» y «< x» a 0.
- Atribución obligatoria: «Anses. 2025. Table de composition nutritionnelle des aliments Ciqual» (README y
  `backend/app/data/FUENTES.md`).
- Energía de lo que no sale de la tabla: 4 proteína, 4 hidratos, 9 grasa, 2 fibra, 7 alcohol (Reglamento UE
  1169/2011).
- Medidas caseras españolas: cucharada de aceite 10 g, de azúcar o miel 15 g, cucharadita 5 g, chorrito 5 g.
- Aceite de cocinar automático: plancha 2 g, horno 3 g, salteado 5 g por 100 g de alimento (mín. 2, máx. 10 por
  ingrediente); frito y rebozado no suman.
- Gasto real: 28 días hasta ayer, días válidos ≥ 50 % del objetivo (mínimo 10), ≥ 4 pesajes que abarquen ≥ 10 días,
  7.700 kcal/kg, `w = min(1, días/21) × min(1, span/21)`, rango aceptable 0,6-1,5 × fórmula, aviso de cambio ≥ 100.
- Entreno: kcal netas (MET − 1) × kg × h.
- Todo en español de España; comentarios con la densidad del código que hay alrededor.
- La app no se rompe con datos antiguos: ingredientes sin `source`/`ref`, comidas viejas y borradores sin conexión.
- Trabajo en la rama `precision-kcal`; commits pequeños; parar limpio hacia el 90 % del plan de Claude (ver
  `PROGRESO-precision.md`).

## Review Focus

1. Alimento de la tabla con una preparación que la tabla no tiene («huevo a la plancha» sin entrada de plancha):
   debe quedarse el valor de la IA, nunca el oficial de otra preparación. → test en Task 1.
2. El usuario nombra la grasa de cualquier forma («AOVE», «un chorrito», «aceite de girasol», «mantequilla»,
   «con manteca»): no se añade aceite automático. → test en Task 3.
3. Comidas por foto: los gramos de la IA no se tocan aunque la tabla sepa el peso de la unidad. → test en Task 3.
4. Comidas e ingredientes antiguos sin `source` ni `ref`: totales iguales y la interfaz los muestra como
   «estimado» sin fallar. → tests en Task 4 (servidor) y Task 8 (vitest).
5. Gasto real con datos malos (sin pesajes, todos los días incompletos, salto de agua de 2 kg): no se ofrece y se
   explica el motivo. → tests en Task 7.

---

### Task 1: Tabla de alimentos — cargador y emparejado (`foodtable.py`)

**Files:**
- Create: `backend/app/foodtable.py`, `backend/app/data/__init__.py` (vacío no hace falta: se lee con `Path`)
- Create: `backend/tests/test_foodtable.py`
- Create (mínimos para los tests; se amplían en Task 2): `backend/app/data/alimentos.json`,
  `backend/app/data/ciqual_2025.tsv`, `backend/app/data/usda_fdc.tsv`, `backend/app/data/recetas.json`

**Interfaces (produce):**
```python
PREPS = ("crudo", "cocido", "plancha", "horno", "salteado", "frito", "rebozado", "guisado", "ninguna")
@dataclass(frozen=True)
class Entry:
    id: str; name: str; food: str; prep: str; ref: str; source: str  # "ciqual" | "usda" | "receta"
    kcal100: float; protein100: float; carbs100: float; fat100: float; fiber100: float; alcohol100: float
    units: dict[str, float]; density: float; oil: bool; default: bool; aliases: tuple[str, ...]
def table() -> "FoodTable"              # carga perezosa y cacheada (lru_cache)
class FoodTable:
    entries: dict[str, Entry]
    def match(self, food: str, prep: str | None = None) -> Entry | None
    def match_name(self, text: str) -> Entry | None   # "arroz blanco cocido", "huevos fritos": separa prep
    def search(self, query: str, limit: int = 8) -> list[Entry]
def prep_from_words(text: str) -> tuple[str, str | None]  # ("pechuga de pollo a la plancha") -> ("pechuga pollo", "plancha")
def food_key(text) -> str  # reutiliza textnorm.food_key
```
Formato de `alimentos.json`: `[{"id","name","food","prep","ref","aliases":[],"units":{},"density":1.0,"oil":false,
"default":false}]`. TSV: `code\tname\tkcal\tprotein\tcarbs\tfat\tfiber\talcohol` con las cifras tal cual (coma
decimal, «-», «< 0,2», «traces»). Recetas: `{"id","name","food","prep","source","yield","ingredients":[["id",g]…],
"units":{}}`; valores por 100 g = suma de ingredientes / (suma de gramos × yield) × 100.

- [ ] **Step 1: tests que fallan** (`test_foodtable.py`), con una tabla mínima de prueba escrita en `tmp_path` y
  `FoodTable.load(dir)`:
  - `parse_value("1,5")==1.5`, `parse_value("-")==0`, `parse_value("< 0,2")==0`, `parse_value("traces")==0`.
  - `match("arroz")` → entrada `default` (arroz blanco cocido); `match("arroz", "crudo")` → arroz crudo.
  - `match("pechuga de pollo", "horno")` → la de `plancha` (intercambiables).
  - `match("huevo", "plancha")` cuando solo hay `cocido` y `frito` → `None` (Review Focus 1).
  - `match("pechuga pavo")` no devuelve pollo; `match("yogur")` no devuelve «yogur griego».
  - `match_name("huevos fritos")` → huevo frito; `match_name("pechuga de pollo a la plancha")` → pollo plancha.
  - Receta: dos ingredientes 100 g + 100 g con yield 0,8 → kcal100 = (k1+k2)/160×100.
  - `prep_from_words("lomo a la brasa") == ("lomo", "plancha")`, `"revuelto"`→`salteado`, `"hervido"`/`"al vapor"`→
    `cocido`, `"asado"`→`horno`, `"empanado"`→`rebozado`.
- [ ] **Step 2:** `cd backend && uv run pytest tests/test_foodtable.py -q` → falla (módulo no existe).
- [ ] **Step 3:** implementar `foodtable.py` (índice `food_key(alias) -> [Entry]`; elección de preparación:
  exacta → `plancha`/`horno` → si `prep in (None, "ninguna")` la `default` → si no, `None`).
- [ ] **Step 4:** tests en verde + `uv run ruff check app tests`.
- [ ] **Step 5:** commit `feat(tabla): tabla de alimentos con CIQUAL 2025 y emparejado estricto`.

### Task 2: Datos — ~600 alimentos, extractos literales y recetas

**Files:**
- Create: `scripts/food_sources.py` (lee el Excel de CIQUAL y los CSV de USDA y escribe los extractos de las filas
  referenciadas en `alimentos.json`; no se ejecuta en CI)
- Modify: `backend/app/data/alimentos.json`, `ciqual_2025.tsv`, `usda_fdc.tsv`, `recetas.json`
- Create: `backend/app/data/FUENTES.md` (atribución, licencias, cómo regenerar)
- Test: `backend/tests/test_foodtable_data.py`

- [ ] **Step 1: tests de datos que fallan**: todo `ref` existe en su extracto; ids únicos; ningún alias apunta a dos
  alimentos distintos con la misma preparación; cada `food` tiene exactamente una `default`; `prep` en `PREPS`;
  macros + alcohol ≤ 105 g/100 g; kcal de la tabla entre 0,85 y 1,15 × la fórmula UE (detecta filas mal leídas);
  `density` entre 0,3 y 1,6; unidades con gramos > 0; están todos los alimentos de las referencias actuales del
  prompt y del banco (`bench.py`); al menos 550 entradas.
- [ ] **Step 2:** descargar USDA FDC (SR Legacy y FNDDS, CSV) a `scratchpad/data/`; escribir `alimentos.json` por
  grupos (cereales y pan, legumbres, carnes, embutidos, pescados y marisco, huevos, lácteos, grasas, frutas,
  verduras, frutos secos, dulces y bollería, bebidas, salsas, platos preparados y comida rápida, suplementos) con
  pesos de unidad comestibles (huevo M 50 g; L 58 g) y densidades (aceite 0,915; leche 1,03; miel 1,42; nata 1,0).
- [ ] **Step 3:** `uv run --with openpyxl python -I scripts/food_sources.py <ciqual.xlsx> <usda_dir>` genera los
  extractos; `recetas.json` con tortilla de patatas, croquetas de jamón, lentejas con chorizo, cocido, fabada,
  salmorejo, ensaladilla rusa, patatas bravas, pisto, albóndigas en salsa, arroz a la cubana, filete empanado,
  migas, gazpacho casero, huevos rotos, bocadillos habituales.
- [ ] **Step 4:** tests en verde; revisar a mano 20 valores al azar frente al Excel.
- [ ] **Step 5:** commit `feat(tabla): 600 alimentos habituales en España con valores literales de CIQUAL y USDA`.

### Task 3: Canalización única `refine.py`

**Files:**
- Create: `backend/app/refine.py`, `backend/tests/test_refine.py`

**Interfaces:**
- Consumes: `foodtable.table()`, `Entry`, `prep_from_words`.
- Produces:
```python
EU_KCAL = {"protein": 4, "carbs": 4, "fat": 9, "fiber": 2, "alcohol": 7}
def eu_kcal(protein, carbs, fat, fiber=0, alcohol=0) -> float
def mentions_fat(text: str) -> bool
def refine(items: list[dict], *, text: str = "", photo: bool = False) -> tuple[list[dict], list[str]]
def official_share(items: list[dict]) -> float   # 0..1, kcal con source en {"tabla","etiqueta","manual"}
```
Cada `item` de entrada: `name, qty, unit, grams, kcal, protein, carbs, fat, fiber?, alcohol?` y opcionales
`food`, `prep`, `product_id`, `manual`, `source`. Salida: mismas claves + `source`, `ref` (si tabla), `food`, `prep`.

- [ ] **Step 1: tests que fallan:**
  - «2 huevos» (`food` huevo, `unit` pieza, `qty` 2, grams 110 de la IA) → grams 100 y valores de la tabla.
  - `unit` ml de aceite 20 → grams 18,3; `vaso` de leche → 200 × 1,03.
  - Foto: mismo huevo con grams 110 → se queda 110 (Review Focus 3), valores de la tabla.
  - Ingrediente sin coincidencia: kcal = `eu_kcal` de sus macros, `source` "ia".
  - «pechuga a la plancha» 150 g sin grasa mencionada → añade «aceite de oliva (para cocinar)» de 3 g y una nota.
  - Dos ingredientes a la plancha (150 g y 600 g) → aceite 3 + 10 (tope) = 13 g en un solo ingrediente.
  - Patatas fritas (entrada `oil: true`) → no se añade aceite; el aceite que traiga la IA marcado como de
    cocinar (`food` aceite y el texto no lo menciona) se elimina.
  - `mentions_fat` es True para «AOVE», «un chorrito», «aceite de girasol», «mantequilla», «con manteca», «margarina»
    y False para «tostada con tomate» (Review Focus 2); con grasa mencionada no se añade aceite y se respeta el de
    la IA.
  - Ingredientes de producto (`product_id`) y manuales pasan intactos con `source` «etiqueta»/«manual».
  - Duplicados: se funden (reutilizar la lógica de `ai.merge_duplicates` sobre dicts).
  - `official_share` con 300 kcal de tabla y 100 de IA → 0,75.
- [ ] **Step 2:** falla. **Step 3:** implementar. **Step 4:** verde + ruff.
- [ ] **Step 5:** commit `feat(comidas): canalización única con valores oficiales, gramos, aceite y energía UE`.

### Task 4: IA y rutas usan la tabla

**Files:**
- Modify: `backend/app/ai.py` (prompt con `food`/`prep`; referencias y raciones generadas desde la tabla; la IA no
  añade aceite de cocinar; `AiItem` acepta `food`, `prep`; `parse_meal` deja de corregir con 4/4/9: lo hace `refine`)
- Modify: `backend/app/routers/meals.py` (`_draft_from_ai` → `refine(..., photo=...)`; `official_share` en el
  borrador), `routers/planner.py`, `routers/suggest.py` (pasar por `refine` antes de sumar)
- Modify: `backend/app/bench.py` (usa la misma canalización; opción `--raw` para medir el código antiguo)
- Test: `backend/tests/test_ai.py`, `test_photo.py`, `test_planner.py`, `test_suggest.py`, `test_api.py`

- [ ] **Step 1: tests que fallan:** el prompt contiene las referencias generadas (p. ej. la línea de «arroz blanco
  cocido» con los valores de la tabla) y el enum de preparaciones; una respuesta simulada con
  `{"food":"huevo","prep":"cocido",...}` da en `/api/meals/resolve` los valores de la tabla, `source` «tabla» y
  `official_share`; una respuesta antigua sin `food`/`prep` sigue funcionando (deduce del nombre) y los totales son
  la suma de ingredientes (Review Focus 4); la foto no cambia gramos; el plan y las sugerencias salen con valores de
  la tabla.
- [ ] **Step 2-4:** rojo → implementar → verde (toda la batería de pytest).
- [ ] **Step 5:** commit `feat(ia): la IA identifica y pesa; los valores salen de la tabla oficial`.

### Task 5: Sin IA — tabla en la resolución, caché con origen y búsqueda

**Files:**
- Modify: `backend/app/models.py` (`Food.source: str = "ia"`, `Food.ref: str | None`; `Targets.tdee_mode: str =
  "formula"`, `Targets.tdee_real: int | None`), `backend/app/migrations.py` (`_v4_precision`: reconstruir `foods` y
  `targets` y re-emparejar la caché con la tabla)
- Modify: `backend/app/matching.py` (`resolve_from_foods` con prep y tabla; `learn_foods` guarda valores de tabla),
  `backend/app/services.py` (`resolve_with_food_cache`: usuario → tabla → caché IA; `store_foods` con origen),
  `backend/app/routers/meals.py` (después de productos, todo pasa por `refine`; `GET /api/foods/table?q=`)
- Test: `test_matching.py`, `test_migrations.py`, `test_api.py`

- [ ] **Step 1: tests que fallan:** «200 g de arroz y 150 g de pollo a la plancha» se resuelve sin IA (status
  `cache`, `ai` simulada no llamada) con valores de la tabla + 3 g de aceite; «2 huevos fritos y una tostada» sin
  IA; una entrada de caché `source="usuario"` gana a la tabla; una de caché de la IA pierde frente a la tabla;
  migración v4 desde una base v3 con una fila de caché «arroz blanco cocido» con valores de la IA → queda con los
  de la tabla y `source="tabla"`; `GET /api/foods/table?q=pollo` devuelve entradas con `ref` y valores.
- [ ] **Step 2-4:** rojo → implementar → verde.
- [ ] **Step 5:** commit `feat(comidas): resolución sin IA con la tabla oficial y caché con origen`.

### Task 6: Entrenos con kcal netas y MET de cardio

**Files:**
- Modify: `backend/app/workouts.py` (`estimated_kcal(duration_min, intensity, weight_kg, cardio=[(exercise_key,
  minutes)])`, `CARDIO_MET`), `routers/training.py` si calcula kcal, `frontend/src/lib/training.ts` si duplica la
  fórmula
- Test: `backend/tests/test_training.py`, `frontend/src/lib/training.test.ts`

- [ ] **Step 1: tests que fallan:** 60 min de fuerza moderada a 80 kg → (5,0 − 1) × 80 = 320 (antes 400); 30 min de
  cinta moderada dentro de un entreno de 60 → 30 min de cardio con su MET y 30 de fuerza; sin duración → 0.
- [ ] **Step 2-4:** rojo → implementar (MET del Compendium 2024: consultar la tabla oficial y citar el código de
  actividad en el comentario) → verde.
- [ ] **Step 5:** commit `fix(entreno): calorías netas sin contar dos veces el basal y MET propio del cardio`.

### Task 7: Gasto real (`expenditure.py`) y objetivos con él

**Files:**
- Create: `backend/app/expenditure.py`, `backend/tests/test_expenditure.py`
- Modify: `backend/app/nutrition.py` (`calculate_targets(..., maintenance_override: float | None = None)`),
  `backend/app/services.py` (`plan_for`/`apply_plan` con `tdee_mode`), `backend/app/routers/profile.py`
  (`GET /api/expenditure`, `POST /api/expenditure/apply`, `POST /api/expenditure/formula`),
  `backend/app/daytargets.py` + `frontend/src/lib/dayTargets.ts` + `fixtures/day_target_cases.json` (con gasto
  real, el entreno no se suma)

**Interfaces:**
```python
def estimate(*, intake: dict[str, float], targets_by_day: dict[str, float], weights: dict[str, float],
             formula_tdee: float, today: date) -> dict
# {"status": "ok"|"insuficiente"|"dudoso", "reason": str|None, "observed": int|None, "estimate": int|None,
#  "formula": int, "weight": float, "days": int, "weighins": int, "span_days": int, "slope_kg_week": float|None}
```
- [ ] **Step 1: tests que fallan:** simulación de 28 días comiendo 2.200 con gasto verdadero 2.500 (pérdida
  300 × 28 / 7.700 kg repartida linealmente con ruido ±0,4 kg determinista) → `observed` dentro de ±3 % de 2.500;
  con 21 días y 21 de span `w == 1`; 9 días válidos → «insuficiente»; 3 pesajes → «insuficiente»; días por debajo
  del 50 % excluidos; salto de agua de 2 kg en el último pesaje → «dudoso» si sale de 0,6-1,5 × fórmula (Review
  Focus 5); `calculate_targets(maintenance_override=2400)` usa 2.400 como mantenimiento; aplicar guarda
  `tdee_mode="real"` y recalcula; volver a la fórmula lo deshace; con modo real `targets_for(...,
  exercise_kcal=300)` no suma.
- [ ] **Step 2-4:** rojo → implementar → verde.
- [ ] **Step 5:** commit `feat(objetivos): gasto real a partir de lo que comes y de tu peso`.

### Task 8: Interfaz

**Files:** (usar la skill frontend-design; seguir los componentes y tokens existentes)
- Modify: `frontend/src/lib/types.ts` (`Item.source?`, `Item.ref?`, `Draft.official_share?`, tipos de gasto real),
  `frontend/src/components/MealBreakdown.tsx` (marca por ingrediente y cuota oficial; `rescale` conserva
  `source`/`ref`), `frontend/src/components/IngredientForm.tsx` + `frontend/src/lib/foods.ts` (resultados de la tabla
  vía `GET /api/foods/table`), la página de objetivos/perfil (tarjeta de gasto real), Ajustes (aviso del entreno)
- Test: vitest de `foods.test.ts`, nuevo `source.test.ts` (etiqueta y cuota para ingredientes sin `source`), e2e
  si cambia un flujo cubierto

- [ ] **Step 1:** tests vitest que fallan (cuota con ingredientes antiguos = 0 sin errores; etiqueta de origen).
- [ ] **Step 2-4:** implementar, `npm run test`, `npm run build`, `npm run lint` si existe, e2e local.
- [ ] **Step 5:** verificar en el navegador (skill webapp-testing) en móvil y escritorio, claro y oscuro.
- [ ] **Step 6:** commit `feat(interfaz): origen de cada valor, búsqueda en la tabla y tarjeta de gasto real`.

### Task 9: Banco, documentación y despliegue

**Files:**
- Modify: `backend/app/bench.py` (40 comidas; referencias calculadas a partir de CIQUAL por ingrediente),
  `README.md` («Cómo calcula las calorías», atribución, capturas si cambian), `docs/DECISIONES.md`
- [ ] **Step 1:** medir antes: copiar el `bench.py` nuevo al contenedor actual y ejecutar `--raw --rpm 3` en segundo
  plano; guardar el resultado.
- [ ] **Step 2:** suite completa (pytest, vitest, voz, e2e) en verde; merge a `main`; push.
- [ ] **Step 3:** desplegar con `deploy/deploy.sh` (copia previa de la base; migración v4); comprobar salud,
  `PRAGMA user_version = 4`, cuentas y comidas iguales que antes.
- [ ] **Step 4:** medir después con el banco nuevo; documentar antes/después en `docs/DECISIONES.md` y README.
- [ ] **Step 5:** commit y push de la documentación; actualizar memoria.

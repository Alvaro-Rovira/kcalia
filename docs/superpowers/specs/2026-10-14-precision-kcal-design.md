# Precisión de calorías — diseño

Fecha: 2026-10-14 · Rama: `precision-kcal` · Estado: aprobado por el usuario («haz lo que creas conveniente»)

## Objetivo

Que las kcal de Kcalia sean prácticamente exactas en todo lo que no depende del modelo de IA. La IA queda solo
para lo que únicamente ella puede hacer: **reconocer qué alimento es** y **estimar cuánto hay cuando nadie lo
dice** (sobre todo en fotos). Los valores nutricionales, los pesos de las unidades, las densidades, el aceite de
cocinar y la energía los pone el código con datos oficiales y reglas fijas y probadas.

Alcance acordado: lo que se come (comidas) **y** lo que se gasta (objetivo diario y entrenos).

Criterios de éxito:
- Ningún valor por 100 g de un alimento de la tabla se aparta de su fuente oficial (test automático).
- La misma comida da siempre las mismas kcal, con IA o sin ella, si los alimentos y cantidades coinciden.
- Banco de comidas real (40 comidas, clave real, en la VPS): el error medio de kcal no empeora en ninguna comida
  con cantidades explícitas y baja en las ambiguas y en las que antes tenían doble conteo de aceite.
- El gasto real calculado con datos simulados recupera el gasto verdadero con un error de ±3 % en 28 días.

## Qué falla hoy (medido leyendo el código)

1. La IA inventa las kcal y los macros por 100 g de todo lo que no está en las ~70 referencias del prompt.
2. La caché de ingredientes aprende de la IA: un valor erróneo se queda guardado y se reutiliza sin IA.
3. Los pesos de unidad («huevo M 55 g», con cáscara en vez de parte comestible), las densidades (ml = g para el
   aceite o la miel) y el aceite de cocinar los aplica la IA siguiendo el prompt, sin garantía.
4. Doble conteo de grasa: «patatas fritas» ya llevan su aceite en los valores por 100 g y además se suma aceite.
5. Las kcal de la IA solo se corrigen si son imposibles (menos del 80 % de 4/4/9). No se usan los factores de la UE
   (la fibra cuenta 2 kcal/g en las etiquetas europeas).
6. Entrenos: kcal brutas (MET × kg × h). Si se suman al objetivo, el metabolismo basal de esa hora cuenta dos veces.
   El cardio usa el MET de las pesas.
7. El gasto diario sale solo de Mifflin-St Jeor × factor de actividad (error típico ±10-20 %) y nunca se contrasta
   con lo que de verdad pasa con el peso.

## 1. Tabla de alimentos

**Fuentes** (todas reutilizables con atribución; ninguna cifra se altera):
- **CIQUAL 2025** (ANSES, Licence Ouverte; cita obligatoria: «Anses. 2025. Table de composition nutritionnelle des
  aliments Ciqual»). Columnas usadas: energía Reglamento UE 1169/2011 (kcal), proteína N × 6,25, glucides
  (hidratos disponibles), lipides, fibra, alcohol. «-» y «traces» = 0; «< x» = 0.
- **USDA FoodData Central** (dominio público, CC0) solo para lo que CIQUAL no tiene (proteína whey, skyr…).
- **Recetas estándar Kcalia** para platos españoles que no están en ninguna (tortilla de patatas, croquetas de
  jamón, lentejas con chorizo, cocido, fabada, salmorejo, ensaladilla, patatas bravas…): ingredientes de la tabla,
  pesos de una receta tipo documentada y factor de rendimiento por pérdida de agua (método de receta EuroFIR). Se
  marcan como «receta», nunca como dato de CIQUAL.

**Ficheros** (en `backend/app/data/`):
- `ciqual_2025.tsv`: extracto **literal** de las filas usadas (código, nombre francés y las seis columnas). Lo genera
  `scripts/food_sources.py` desde el Excel oficial (no se sube el Excel).
- `usda_fdc.tsv`: lo mismo para las pocas filas de USDA.
- `alimentos.json`: lo que escribo yo. Por alimento: `id`, `name` (español), `food` (alimento base), `prep`,
  `aliases`, `ref` (`ciqual:36018`, `usda:…` o `receta:…`), `units` (gramos de una pieza, rebanada, loncha, plato…),
  `density` (g/ml), `oil` (true si los valores ya incluyen la grasa de freír), `default` (la preparación que se
  supone si no se dice ninguna).
- `recetas.json`: ingredientes (id de la tabla + gramos), rendimiento y fuente de la receta.

**Preparaciones** (enum común a tabla, IA y texto): `crudo`, `cocido` (hervido, al vapor), `plancha` (plancha,
parrilla, a la brasa), `horno` (asado), `salteado` (salteado, revuelto, a la sartén), `frito`, `rebozado`, `guisado`,
`ninguna` (se come tal cual: pan, yogur, embutido, fruta…).

Cobertura objetivo: unos 600 alimentos habituales en España (incluidas las 70 referencias actuales del prompt y todo
lo que aparece en el banco de pruebas). Alimentos de marca: siguen saliendo de «Mis productos» y Open Food Facts.

**Módulo `foodtable.py`**: carga perezosa una vez por proceso. `match(food, prep) -> Entry | None` con emparejado
**estricto**: el alimento normalizado (minúsculas, sin tildes, singular, sin artículos) debe ser igual a `food` o a un
alias. Nada de parecidos difusos. Preparación: exacta; `plancha`↔`horno` son intercambiables; sin preparación (o
`ninguna`) vale la entrada `default`. Si se pide `frito`/`rebozado`/`crudo` y la tabla no tiene esa preparación,
**no hay coincidencia**: mejor el valor de la IA que uno oficial de otra preparación.

## 2. Una sola canalización para todas las comidas (`refine.py`)

`refine(items, *, text, photo) -> (items, notes)` se aplica a texto, voz, foto, plan semanal, sugerencias y
resolución sin IA, en este orden:

1. **Emparejar** cada ingrediente con la tabla (`food` + `prep` que da la IA; si falta, se deduce del nombre).
2. **Gramos** (salvo en fotos, donde manda la estimación visual): `g`/`kg` tal cual; `ml`/`cl`/`l`/`vaso`/`taza`
   con la densidad; `pieza`/`rebanada`/`loncha`/`lata`/`plato`/`cda`/`cdta`… con `units` de la tabla. Si la tabla no
   sabe el peso de esa unidad, se quedan los gramos de la IA.
3. **Valores**: con coincidencia, los de la tabla (`source: "tabla"`, `ref`). Sin ella, los de la IA con la energía
   recalculada siempre con los factores de la UE: 4 proteína, 4 hidratos, 9 grasa, 2 fibra, 7 alcohol
   (`source: "ia"`).
4. **Aceite de cocinar** (si el texto no menciona aceite, mantequilla, margarina, manteca ni «chorrito»): el código
   añade un único ingrediente «aceite de oliva (para cocinar)» según la preparación de cada alimento que no lo traiga
   ya incluido: plancha 2 g, horno 3 g, salteado 5 g por cada 100 g de alimento (mínimo 2 g y máximo 10 g por
   ingrediente). Frito y rebozado no suman aceite: los valores de esa preparación ya incluyen la grasa absorbida. Si
   el usuario menciona la grasa, manda lo que dice y no se añade nada. La IA ya no añade aceite de cocinar; sí puede
   proponer el aliño de una ensalada.
5. **Fundir duplicados** y redondear a un decimal.

Cada ingrediente guarda `source` (`tabla`, `etiqueta`, `ia`, `manual`) y `ref`. La comida devuelve qué parte de sus
kcal tiene valores oficiales (tabla, etiqueta o manual).

**Prompt de la IA**: añade por ingrediente `food` y `prep` (enum). Ya no hace falta que se aprenda valores: la lista
«VALORES DE REFERENCIA» y «RACIONES TÍPICAS» se **generan desde la tabla**, así lo que la IA ve y lo que el código
aplica son lo mismo. Las convenciones españolas de medidas caseras se mantienen (cucharada de aceite 10 g, de
azúcar o miel 15 g, cucharadita 5 g, chorrito 5 g).

## 3. Sin IA: tabla antes que IA

Orden de resolución: historial exacto → historial parecido → productos con etiqueta → **ingredientes** → IA.
Para cada trozo del texto («200 g de arroz», «2 huevos fritos») se separan cantidad, unidad, alimento y preparación
(las palabras de preparación del texto se traducen al enum), y se busca en: caché de lo que el usuario corrigió a
mano → tabla → caché aprendida de la IA. Si todos los trozos se resuelven, la comida sale sin IA, con los mismos
pasos de `refine` (gramos, aceite).

La caché (`foods`) gana las columnas `source` y `ref`. Cuando el alimento está en la tabla se guardan los valores de
la tabla y no los de la IA. Una migración re-empareja la caché existente y corrige las filas que coincidan. Las
comidas ya apuntadas no se tocan.

El formulario de «añadir ingrediente a mano» busca también en la tabla (`GET /api/foods/table?q=`).

## 4. Gasto

**Gasto real (`expenditure.py`)**: con los últimos 28 días hasta ayer.
- Días válidos: con comidas y con al menos el 50 % del objetivo de ese día (los demás casi seguro están incompletos).
  Hacen falta 10.
- Peso: pendiente por mínimos cuadrados de los pesajes de la ventana. Hacen falta 4 que abarquen 10 días o más.
- Gasto observado = media de kcal de los días válidos − pendiente (kg/día) × 7.700.
- Se mezcla con la fórmula según los datos: `w = min(1, días/21) × min(1, días_entre_pesajes/21)`.
- Si el observado se sale de 0,6-1,5 veces la fórmula, no se ofrece y se explica por qué (registros incompletos o
  agua).
- Tarjeta en Objetivos con el gasto real frente al de la fórmula, los datos usados y un botón «Usar mi gasto real».
  `targets` guarda `tdee_mode` (`formula`/`real`) y el valor aplicado. El plan se recalcula con ese mantenimiento.
  Si después difiere 100 kcal o más, la tarjeta propone actualizarlo.
- Con el gasto real activo, «sumar el entreno al objetivo» queda desactivado: ese gasto ya incluye los entrenos.

**Entrenos (`workouts.py`)**: kcal **netas** = (MET − 1) × kg × h. Las series de ejercicios en minutos (cardio)
usan el MET de su actividad e intensidad (Compendium of Physical Activities 2024). El resto de la duración, el de
fuerza. En Ajustes, si se suma el entreno con actividad «moderada» o más, se avisa de que el factor de actividad ya
cuenta el gimnasio.

## 5. Interfaz

- Desglose de la comida: cada ingrediente con una marca discreta de su origen (oficial / etiqueta / estimado / a
  mano). Encima, qué parte de las kcal tiene valores oficiales.
- Formulario de ingrediente: resultados de la tabla con su fuente.
- Objetivos: tarjeta de gasto real. Ajustes: aviso del entreno.
- README: nueva sección «Cómo calcula las calorías» y atribución de CIQUAL y USDA.

## 6. Pruebas y verificación

- TDD en todos los módulos: tabla (valores literales frente al extracto; todo `ref` existe; alias sin choques),
  emparejado, gramos, aceite, energía UE, recetas, resolución sin IA, gasto real (datos simulados) y entrenos.
- Los tests y el e2e existentes siguen en verde (pytest, vitest, voz y Playwright).
- `bench.py` pasa a 40 comidas (más platos españoles y casos de aceite), con referencias calculadas a partir de
  CIQUAL. Se mide antes (código desplegado) y después, con la clave real en la VPS (≈ 0,25 $ en total).
- Despliegue con copia previa de la base, comprobación en producción y documentación (README, DECISIONES).

## Fuera de alcance

Cambiar de modelo de IA, ajustar la calidad de las fotos, la detección de tamaño de ración por visión y las
fórmulas con porcentaje de grasa corporal (la app no lo registra).

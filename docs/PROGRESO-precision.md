# Progreso — precisión de calorías

Rama `precision-kcal`. Plan: `docs/superpowers/plans/2026-10-14-precision-kcal.md`.
Si la sesión se para (límite del plan de Claude), retomar por la primera tarea sin marcar.

- [x] Task 1: tabla — cargador y emparejado
- [x] Task 2: datos (600 alimentos, extractos, recetas)
- [x] Task 3: canalización `refine.py`
- [x] Task 4: IA y rutas usan la tabla
- [x] Task 5: sin IA, caché con origen, migración v4, búsqueda
- [x] Task 6: entrenos con kcal netas
- [x] Task 7: gasto real
- [ ] Task 8: interfaz
- [ ] Task 9: banco, documentación y despliegue

Ficheros de trabajo fuera del repo (se pueden volver a descargar): Excel de CIQUAL 2025 en
`https://ciqual.anses.fr/cms/sites/default/files/inline-files/Table%20Ciqual%202025_FR_2025_11_03.xlsx`.

Después del despliegue (pedido por el usuario el 2026-10-14): analizar Kimi K2.6 frente a Haiku 5.5 para analizar
comidas y darle un veredicto de cuál calculará mejor las kcal (con la canalización nueva, la IA solo identifica y
pesa). Usar la skill claude-api para datos de Haiku 5.5; medir con `bench.py` si hay clave de Anthropic.

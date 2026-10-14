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
- [x] Task 8: interfaz (revisada en el navegador, móvil, claro y oscuro)
- [x] Task 9: banco, documentación y despliegue (09ee50e en producción el 2026-10-14; migración v4 aplicada sin pérdida de datos)

Ficheros de trabajo fuera del repo (se pueden volver a descargar): Excel de CIQUAL 2025 en
`https://ciqual.anses.fr/cms/sites/default/files/inline-files/Table%20Ciqual%202025_FR_2025_11_03.xlsx`.

Después del despliegue (pedido por el usuario el 2026-10-14): analizar Kimi K2.6 frente a Haiku 5.5 para analizar
comidas y darle un veredicto de cuál calculará mejor las kcal (con la canalización nueva, la IA solo identifica y
pesa). Usar la skill claude-api para datos de Haiku 5.5; medir con `bench.py` si hay clave de Anthropic.

## Estado al parar (2026-10-14, uso del plan al 78 %)

Rama `precision-kcal`, todo con commit (último: interfaz). Pruebas en verde: pytest 636, vitest 198, e2e 27.
Producción sigue con el código anterior (a9b0511); no se ha desplegado nada.

Medición «antes» (código desplegado, `--raw`, 40 comidas, clave real; salida completa en la VPS en
`/root/kcalia-bench-antes.txt`): error medio de kcal 15,8 % frente a la tabla oficial, 21/30 dentro de ±12 %,
ambiguas 8/10, 2.600 tokens de entrada y 147 de salida por comida, mediana 4,2 s. Fallos típicos: huevo frito
197 kcal (oficial 88), 150 g de patatas fritas 468 (387, aceite contado dos veces), café con leche 157 (73).

### Siguiente (en este orden)
1. Revisar en el navegador (skill webapp-testing, móvil y escritorio, claro y oscuro): iconos de origen y barra de
   «% de kcal con valores oficiales» en el desglose, búsqueda de la tabla al añadir un ingrediente, tarjeta «Tu gasto
   real» en Ajustes → Tu plan, aviso del interruptor del entreno. Marcar Task 8 en el ledger.
2. Revisión final de toda la rama (requesting-code-review/code-reviewer.md) y arreglos con TDD.
3. Task 9: README («Cómo calcula las calorías» + atribución CIQUAL/USDA), docs/DECISIONES.md, merge a main, push,
   `deploy/deploy.sh` (copia previa, migración v4), comprobar `PRAGMA user_version = 4`, y medir «después»:
   `docker compose exec app python -m app.bench --rpm 3 --price-in 0.95 --price-out 4.00`.
4. Comparativa Kimi K2.6 frente a Haiku 5.5 (pedida por el usuario).

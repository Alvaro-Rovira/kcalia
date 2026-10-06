# Progreso · mejoras-v2

Memoria del trabajo autónomo. Si la sesión se reinicia: leer este fichero, `docs/DECISIONES.md` y `git log`, y
seguir por la primera tarea sin marcar. Diseño en `docs/superpowers/specs/2026-10-06-mejoras-v2-design.md`.

Estado inicial (2026-10-06, commit 6b1b693): 205 pytest, 111 Vitest, typecheck, ruff y build en verde.
Producción: 1 usuario, 3 comidas, 2 productos, 1 peso (solo recuentos).

Orden: la infraestructura y el multiusuario (5.4, 5.5) van primero; ver DECISIONES.

## Fase 0 · Base
- [x] 0.0 Paso 0: rama `mejoras-v2`, árbol limpio
- [x] 0.1 Migraciones con `PRAGMA user_version`, copia previa y prueba sobre base de demostración

## Fase 5 (adelantada) · Acceso y seguridad
- [x] 5.4 Multiusuario con aprobación manual, aislamiento por `user_id`, límites de gasto
- [x] 5.5 Panel de administración `/admin` con auditoría

Tras 5.5: 304 pytest, 111 Vitest, 11 e2e en verde.

## Fase 1 · Registro diario
- [x] 1.1 Ingrediente a mano dentro de una comida, con autocompletado de la caché
- [x] 1.2 Copiar comida y día entero
- [x] 1.3 Favoritos y recientes ordenados por momento del día
- [x] 1.4 Escáner de códigos de barras con Open Food Facts

Tras la fase 1: 319 pytest, 133 Vitest, 14 e2e en verde.

## Fase 2 · Seguimiento
- [x] 2.1 Agua
- [x] 2.2 Fibra y alcohol
- [x] 2.3 Medidas corporales y fotos de progreso

Tras la fase 2: 347 pytest, 141 Vitest, 17 e2e en verde.

## Fase 3 · Entrenamiento
- [x] 3.1 Tipo de día entreno/descanso con objetivos propios
- [x] 3.2 Registro de entrenamientos `/entreno`
- [x] 3.3 Estimación de calorías de entreno

Tras la fase 3: 383 pytest, 156 Vitest, 19 e2e en verde.

## Fase 4 · Constancia y utilidad
- [x] 4.1 Recordatorios con Web Push
- [x] 4.2 Planificador semanal y lista de la compra
- [x] 4.3 Sugerencia para cerrar el día
- [x] 4.4 Compartir el resumen semanal como imagen

Tras la fase 4: 413 pytest, 176 Vitest, 23 e2e en verde.

## Fase 5 · Datos
- [x] 5.1 Copia de seguridad fuera del servidor
- [x] 5.2 Importar datos (CSV y JSON propio)
- [x] 5.3 Atajos de la PWA y atajo de iOS por voz

Tras la fase 5: 431 pytest, 182 Vitest, 25 e2e en verde.

## Fase final
- [ ] A Revisión global, README, .env.example, capturas, RESUMEN-FINAL
- [ ] B Merge en main y push
- [ ] C Localizar servidor
- [ ] D Copia previa y comprobaciones en el servidor
- [ ] E Despliegue
- [ ] F Verificación en producción
- [ ] H Cierre

## Notas para retomar
- Batería: `cd backend && uv run ruff check app tests && uv run pytest -q`; `cd frontend && npx tsc -b --noEmit && npm test
  && npm run build`; e2e: `uv run --project backend --group e2e pytest e2e -q` (19 en verde tras la fase 3).
- ruff de `scripts/` solo para gen-vapid.py y make-admin.py (los demás scripts ya tenían líneas largas antes).
- Pendiente: 5.2, 5.3 y la fase final (README para GitHub, capturas, merge, push, redespliegue en el
  Docker dedicado de Kcalia en la VPS y verificación). Pausado a petición del usuario tras 4.2; seguir cuando lo diga.


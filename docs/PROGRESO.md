# Progreso · mejoras-v2

Memoria del trabajo autónomo. Si la sesión se reinicia: leer este fichero, `docs/DECISIONES.md` y `git log`, y
seguir por la primera tarea sin marcar. Diseño en `docs/superpowers/specs/2026-10-06-mejoras-v2-design.md`.

Estado inicial (2026-10-06, commit 6b1b693): 205 pytest, 111 Vitest, typecheck, ruff y build en verde.
Producción: 1 usuario, 3 comidas, 2 productos, 1 peso (solo recuentos).

Orden: la infraestructura y el multiusuario (5.4, 5.5) van primero; ver DECISIONES.

## Fase 0 · Base
- [x] 0.0 Paso 0: rama `mejoras-v2`, árbol limpio
- [ ] 0.1 Migraciones con `PRAGMA user_version`, copia previa y prueba sobre base de demostración

## Fase 5 (adelantada) · Acceso y seguridad
- [ ] 5.4 Multiusuario con aprobación manual, aislamiento por `user_id`, límites de gasto
- [ ] 5.5 Panel de administración `/admin` con auditoría

## Fase 1 · Registro diario
- [ ] 1.1 Ingrediente a mano dentro de una comida, con autocompletado de la caché
- [ ] 1.2 Copiar comida y día entero
- [ ] 1.3 Favoritos y recientes ordenados por momento del día
- [ ] 1.4 Escáner de códigos de barras con Open Food Facts

## Fase 2 · Seguimiento
- [ ] 2.1 Agua
- [ ] 2.2 Fibra y alcohol
- [ ] 2.3 Medidas corporales y fotos de progreso

## Fase 3 · Entrenamiento
- [ ] 3.1 Tipo de día entreno/descanso con objetivos propios
- [ ] 3.2 Registro de entrenamientos `/entreno`
- [ ] 3.3 Estimación de calorías de entreno

## Fase 4 · Constancia y utilidad
- [ ] 4.1 Recordatorios con Web Push
- [ ] 4.2 Planificador semanal y lista de la compra
- [ ] 4.3 Sugerencia para cerrar el día
- [ ] 4.4 Compartir el resumen semanal como imagen

## Fase 5 · Datos
- [ ] 5.1 Copia de seguridad fuera del servidor
- [ ] 5.2 Importar datos (CSV y JSON propio)
- [ ] 5.3 Atajos de la PWA y atajo de iOS por voz

## Fase final
- [ ] A Revisión global, README, .env.example, capturas, RESUMEN-FINAL
- [ ] B Merge en main y push
- [ ] C Localizar servidor
- [ ] D Copia previa y comprobaciones en el servidor
- [ ] E Despliegue
- [ ] F Verificación en producción
- [ ] H Cierre

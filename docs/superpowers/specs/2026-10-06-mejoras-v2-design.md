# Kcalia · mejoras v2 · diseño

Fecha: 2026-10-06. Rama: `mejoras-v2`. Fuente de requisitos: el encargo del usuario (fases 1 a 5 y fase final),
que hace de especificación aprobada porque pidió trabajo 100 % autónomo y sin preguntas.

## Objetivo

Pasar de una app de un solo usuario a una instalación multiusuario con aprobación manual, sin que nadie pueda
gastar el crédito de IA del administrador, y añadir registro diario (ingredientes a mano, copiar, escáner),
seguimiento (agua, fibra, alcohol, medidas, fotos), entrenamiento, constancia (recordatorios, planificador,
sugerencia de cierre del día, compartir) y datos (copia externa, importación, atajos).

## Orden de ejecución

1. **Infraestructura de migraciones** (`backend/app/migrations.py`): `PRAGMA user_version`, una función por versión,
   copia de seguridad previa automática y reconstrucción de tablas al estilo oficial de SQLite (crear `_new_x`,
   copiar, borrar, renombrar, recrear índices). Hoy no existe: `init_db` solo hace `create_all`.
2. **5.4 multiusuario y 5.5 administración**, antes que el resto: todas las tablas nuevas nacen ya con `user_id` y no
   hay que rehacerlas. El usuario lo numeró al final, pero hacerlo primero evita reescribir cada funcionalidad.
3. Fases 1 a 4, 5.1 a 5.3 y fase final.

## Aislamiento por usuario (seguro por defecto)

- Mezcla `TenantMixin` con `user_id` (FK a `users`, `ON DELETE CASCADE`) en todas las tablas de datos.
- La sesión de SQLAlchemy lleva el usuario en `session.info["user_id"]`. Un evento `do_orm_execute` añade
  `with_loader_criteria(TenantMixin, user_id == X)` a toda consulta ORM (SELECT, UPDATE y DELETE masivos), y un
  `before_flush` rellena `user_id` en lo que se inserta. Si una consulta toca una tabla de datos sin usuario y sin
  permiso explícito (`all_users`), se lanza un error: olvidarse de filtrar falla en las pruebas, no filtra datos.
- Restricciones únicas por usuario: `(user_id, norm)` en comidas conocidas e ingredientes, `(user_id, date)` en
  pesos, `(user_id, client_id)` en comidas, `(user_id, key)` en contadores y logros, `(user_id, date, kind)` en uso
  de IA, `(user_id, week_start)` en resúmenes.
- Dependencia global en la app (`enforce_access`): toda ruta `/api/*` exige usuario **aprobado** salvo las públicas
  (`/api/health`, `/api/auth/login`, `/api/auth/register`, `/api/auth/status` = sesión actual, y `/api/auth/logout`
  porque una cuenta pendiente o bloqueada debe poder salir). Un endpoint nuevo queda protegido sin hacer nada.
  `/api/admin/*` exige además `require_admin` (403). Una prueba recorre todas las rutas registradas.

## Cuentas

- `users`: `status` (`pending`, `approved`, `suspended`), `is_admin` (índice único parcial: como mucho uno),
  `last_seen_at`, `ai_daily_limit` y `stt_daily_limit` opcionales.
- Migración: los usuarios existentes quedan `approved`; el más antiguo, administrador. Si no hay ninguno, la primera
  cuenta que se registre será administradora y aprobada (instalación nueva) y adopta los datos huérfanos.
- Registro: abierto si `ALLOW_SIGNUP` y el interruptor del admin lo permiten; nace `pending`; respuesta idéntica
  exista o no el usuario (no inicia sesión); honeypot; validación de nombre y contraseña; límite por IP; tope
  `MAX_PENDING_ACCOUNTS`. Login: espera creciente por IP y por usuario, verificación de hash simulada si el usuario
  no existe (sin oráculo de tiempo), mensaje genérico.
- Una cuenta `pending`/`suspended` puede iniciar sesión pero solo ve su estado y puede salir.

## Límites de gasto

`check_ai_budget(db, user)`: IA en pausa (interruptor del admin) → 503; usuario normal: su límite
(`ai_daily_limit` o `AI_USER_DAILY_LIMIT`) y el global (`AI_DAILY_LIMIT`, suma de todos); admin: solo su límite
(`ADMIN_AI_DAILY_LIMIT`, por defecto igual a `AI_DAILY_LIMIT`). Igual para la voz con `STT_*`. Coste estimado con
precios por variable de entorno.

## Tablas nuevas (todas con `user_id`)

`prefs` (JSON validado por usuario), `app_settings` (global), `admin_audit`, `water_logs`, `body_measurements`,
`progress_photos`, `day_types`, `exercises`, `workouts`, `workout_sets`, `workout_templates`, `push_subscriptions`,
`reminder_log`, `meal_plans`, `shopping_checks`, `barcode_cache` (global, sin datos personales).
Columnas nuevas: `products.barcode` (única por usuario), `foods.fiber100/alcohol100`, `meals.fiber/alcohol`.

## Decisiones técnicas principales

- Web Push implementado con `cryptography` (RFC 8291 aes128gcm + VAPID ES256), sin `pywebpush` (arrastra aiohttp).
  Probado con el vector de prueba de la RFC.
- Copia externa a S3 compatible con firma SigV4 propia sobre `httpx` (sin boto3); cifrado opcional AES-GCM.
  rclone se documenta como alternativa desde el host.
- Escáner: `BarcodeDetector` nativo y, si no existe, `zxing-wasm` cargado bajo demanda.
- Navegación móvil: Hoy · Historial · Entreno · Progreso (resumen, peso y medidas) · Ajustes.
- Sugerencia de cierre del día: función pura en `frontend/src/lib/suggest.ts`, sin IA, en el móvil.

## Pruebas

pytest (API, migración sobre base de demostración, aislamiento, rutas protegidas, límites, push, copia, importación),
Vitest (sugerencias con prueba de propiedades, objetivos por tipo de día, utilidades), Playwright (flujos nuevos en
`e2e/test_flow.py`).

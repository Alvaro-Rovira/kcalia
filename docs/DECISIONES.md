# Decisiones · mejoras-v2

Decisiones tomadas sin poder preguntar, con el motivo. La más reciente, abajo.

1. **Proceso.** El encargo pide autonomía total y sin preguntas: el encargo hace de especificación aprobada y las
   aprobaciones intermedias del proceso de diseño se sustituyen por este fichero. Diseño resumido en
   `docs/superpowers/specs/2026-10-06-mejoras-v2-design.md`.
2. **Orden.** El multiusuario (5.4) y el panel de administración (5.5) se hacen antes que las fases 1 a 4: así cada
   tabla nueva nace con `user_id` y no hay que reescribir cada funcionalidad después.
3. **Migraciones.** No había mecanismo (solo `create_all`). Se usa `PRAGMA user_version` con una función por versión
   y una copia comprimida de la base antes de migrar (`backups/kcalia-premigracion-vN-*.db.gz`).
4. **Aislamiento seguro por defecto.** Filtro automático por usuario en la sesión de SQLAlchemy y error si una
   consulta toca datos sin usuario; además, dependencia global que exige cuenta aprobada en toda ruta `/api`
   salvo las públicas.
5. **Cerrar sesión es pública** junto a health, login, registro y la sesión actual: el encargo exige que una cuenta
   pendiente o bloqueada pueda cerrar sesión. Solo borra la sesión de quien llama.
6. **Registro sin pistas.** La respuesta es la misma exista o no el usuario y no inicia sesión: se entra con el login
   y una cuenta pendiente ve su pantalla de estado. Excepción: en una instalación sin ninguna cuenta, la primera es
   la administradora, queda aprobada y entra directamente (como hasta ahora).
7. **Límite del administrador.** El admin solo está sujeto a su propio límite (`ADMIN_AI_DAILY_LIMIT`, por defecto
   `AI_DAILY_LIMIT`) y al interruptor de pausa, que él mismo controla. El tope global se aplica al resto y cuenta
   el consumo de todos. `STT_USER_DAILY_LIMIT` no tenía valor por defecto en el encargo: 30.

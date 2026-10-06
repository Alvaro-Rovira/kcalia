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
8. **Acciones de administración sin cola offline.** Aprobar, bloquear o borrar cuentas necesita la respuesta del
   servidor en el momento (y quedar en la auditoría): se exige conexión y se avisa si no la hay. La regla de la cola
   se aplica a los datos del diario.
9. **Bloquear no cierra la sesión**: la siguiente petición ya responde 403 y la persona ve «Tu cuenta está
   bloqueada» en lugar de un login sin explicación. Para echarla del todo está «Cerrar sesiones».
10. **Precios del panel en dólares** (los de Moonshot): `AI_PRICE_INPUT`/`AI_PRICE_OUTPUT` por millón de tokens y
    `STT_PRICE_PER_CALL` (0 con el Whisper propio). Es una estimación, no la factura.
11. **Escáner.** `BarcodeDetector` nativo (Android) y, si no existe (Safari en iPhone), `zxing-wasm` cargado bajo
    demanda desde el propio servidor (≈ 420 KB gzip, fuera de la precarga; se guarda en caché la primera vez). La CSP
    añade `'wasm-unsafe-eval'`, que solo permite compilar WebAssembly. Siempre se puede escribir el código a mano.
12. **Open Food Facts** se consulta desde el servidor con User-Agent identificable, 6 s de espera, caché de 30 días
    (3 para «no existe») y un tope de 150 búsquedas por usuario y día. `OFF_BASE_URL` solo existe para las pruebas.
13. **Copias de comidas** cuentan como «a un toque» (`source = recent`), no gastan IA y no vuelven a enseñar a la caché
    los ingredientes hechos a mano.
14. **Fibra y alcohol opcionales** en ingredientes, comidas (migración v3) y caché: lo antiguo queda vacío y cuenta
    como 0. El esquema de la IA pide `fiber100` y `alcohol100`, pero acepta respuestas sin ellos; el alcohol entra en la
    comprobación de coherencia (7 kcal/g). Las bebidas rápidas se guardan como comida con `source = "drink"` y se
    calculan en el móvil: gramos de alcohol = ml × % vol × 0,789 / 100.
15. **Fotos de progreso solo con conexión.** Se reducen en el móvil (1.280 px) y se suben al momento; guardar
    imágenes en la cola offline (IndexedDB) arriesga el espacio del navegador en iOS. Las medidas sí van por la cola.
    Las fotos viven en su propia tabla con la imagen en una columna diferida: los listados nunca la cargan.

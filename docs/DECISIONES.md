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
16. **Objetivos por tipo de día, desactivados por defecto**: activarlos cambiaría el objetivo de quien ya usa la app
    sin pedirlo. Al activarlos: días de entreno por defecto lunes, miércoles y viernes, +200 kcal en entreno y −100 en
    descanso, siempre a través de los hidratos (la proteína y la grasa no cambian). Cada tipo se puede fijar a mano y
    cada día concreto se cambia desde Hoy. El cálculo existe en Python y TS con casos compartidos y redondeo «mitad
    hacia arriba» en los dos (el `round` de Python redondea al par y daba resultados distintos).
17. **Entrenos sin conexión de verdad**: ejercicios, plantillas, sesiones y series llevan `client_id` generado en el
    móvil y las series apuntan al ejercicio por ese id, así que hasta un ejercicio creado sin red se puede usar al
    momento. El catálogo inicial (40 ejercicios) y las rutinas Empuje, Tirón, Pierna y Cuerpo completo se siembran a
    cada usuario la primera vez, con ids fijos. Los ejercicios no se borran, se archivan (conservan su historial).
18. **Navegación móvil**: Hoy · Historial · Entreno · Progreso · Ajustes. «Progreso» agrupa el resumen semanal y el
    cuerpo (peso, medidas y fotos) con dos pestañas; en escritorio la barra lateral muestra todo por separado.
19. **Calorías del entreno**: MET × peso × horas con MET de fuerza 3,5 / 5 / 6 (suave / moderada / intensa, del
    Compendium of Physical Activities). Solo informativas por defecto; si se activa sumarlas, entran en el objetivo de
    ese día como hidratos, con el mismo cálculo en el servidor y en el móvil.
20. **Web Push propio** con `cryptography` (RFC 8291 + VAPID), probado con el vector de la RFC: `pywebpush` arrastra
    aiohttp y requests. Los recordatorios se revisan cada minuto en el propio proceso; cada aviso tiene una franja de
    45 minutos y se anota para no repetirlo. Vienen apagados: el usuario los activa en Ajustes. Las suscripciones que
    responden 404/410 se borran al momento; las que fallan 5 veces seguidas, también.
21. **Sugerencia para cerrar el día**: función pura en `lib/suggest.ts` con prueba de propiedades (2.000 escenarios):
    nunca se pasa de las calorías que quedan medidas como se guardarían (`itemsTotal`). Raciones ×0,5 a ×2, o por
    gramos (máximo 250 g) en ingredientes y productos por 100 g; parejas entre los 14 más usados. De 23 a 5 h apunta a
    algo ligero (≤ 350 kcal). Variedad: lo sugerido ayer y lo descartado hoy se guarda en el propio móvil
    (localStorage); lo ocultado para siempre va en las preferencias. Se guarda con `source = "sugerencia"`.
22. **Copia externa a S3 compatible** (AWS, Cloudflare R2, Backblaze B2, MinIO) con firma SigV4 propia sobre httpx,
    probada con el ejemplo oficial de AWS: boto3 pesa mucho para un PUT, un HEAD, un listado y un DELETE. rclone no va
    dentro del contenedor (es otro binario); se documenta como alternativa desde el host. Cifrado opcional AES-256-GCM
    con clave derivada por scrypt de una frase; `scripts/restore-backup.py` descifra y comprueba la integridad. Hasta 6
    intentos al día; el estado se ve en Administración y, si la última falló, también en Ajustes del admin.
23. **Importar datos**: CSV de MyFitnessPal, Yazio o genérico, con las columnas adivinadas por la cabecera y un mapeo
    manual en la vista previa. Cada fila recibe un `client_id` determinista (`imp-` + SHA-1 de sus datos), así que
    importar dos veces el mismo fichero no duplica nada. Las filas que coinciden con una comida apuntada a mano (mismo
    día, momento y calorías) se señalan y se saltan por defecto. Cada fila del CSV se guarda como una comida con un único
    ingrediente (sus macros totales), con fuente `import`. El JSON de Kcalia solo añade lo que falta y no pisa perfil,
    objetivos ni preferencias que ya existan. Necesita conexión: no pasa por la cola offline.
24. **Atajos**: cuatro atajos en el manifiesto (añadir comida, un vaso de agua, entrenar, peso) y un atajo de Siri que
    abre `/?nueva=1&texto=...`. El texto dictado se rellena pero **no se analiza solo**, para que ningún enlace pueda
    gastar IA. El agua por URL sí se apunta (es inocuo y se puede deshacer), una sola vez por navegación. `haptic()` no
    vibra sin un toque previo en la página: Chrome lo bloquea y lo anota como error.
25. **Despliegue sin tocar secretos**: `deploy/deploy.sh` añade a `.env` solo las variables nuevas de `.env.example`
    (con su valor por defecto, mostrando únicamente los nombres) y genera las claves VAPID dentro del contenedor la
    primera vez, sin que pasen por la pantalla. El contacto VAPID por defecto es `https://DOMAIN` porque Apple rechaza
    `mailto:` con dominios como `localhost`.

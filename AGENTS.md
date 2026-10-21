# AGENTS.md: Kcalia

Archivo de traspaso para cualquier IA que trabaje en este proyecto (Codex, Claude Code…). **Léelo entero antes de
empezar.** Aquí está qué es, cómo se ha llegado hasta aquí, el estado actual, las reglas y lo que falta. El detalle
de producto, de la arquitectura y de las pruebas está en [`README.md`](README.md).

**Mantenlo al día:** al terminar cada tarea, y antes de parar por el límite de uso, actualiza «Estado actual»,
«Historial» y «Pendiente» (aquí y en la sección «Pendiente» del README).

Última actualización: 21 de octubre de 2026.

---

## 1. Qué es

**Kcalia** es una PWA en español para contar calorías y macros pensada para gente que va al gimnasio. Se apunta lo
que comes escribiendo, dictando o con una foto; la IA reconoce los alimentos y las cantidades, y **las calorías salen
de una tabla oficial** (CIQUAL 2025 + USDA), no de la IA. Además:
- objetivos calculados (Mifflin-St Jeor × nivel de actividad × objetivo);
- días de entreno y de descanso;
- gasto real medido con el peso;
- registro de entrenos, agua, medidas y fotos de progreso;
- plan semanal con lista de la compra;
- productos por etiqueta o código de barras;
- importación desde MyFitnessPal o Yazio;
- varias cuentas con aprobación y panel de administración;
- funciona sin conexión.

- **Producción:** https://kcalia.space
- **Repositorio:** https://github.com/Alvaro-Rovira/kcalia (público). La rama de trabajo actual es `haiku`; `main` es lo desplegado.
- **Carpeta local:** `~/Desktop/calculadora gym`, dentro de iCloud (ver «Trampas»).
- **Dueño:** Álvaro Rovira (GitHub `Alvaro-Rovira`). Es el único usuario real por ahora y el administrador.

## 2. Cómo trabajar con el dueño

- **Idioma:** habla siempre en **español**, con explicaciones sencillas y sin jerga. No es programador.
- **Propón antes de hacer.** Para trabajo nuevo, primero opciones con lo que aporta cada una y su esfuerzo, y una
  recomendación. Espera su OK. Con el OK, trabaja solo hasta terminar, probando y desplegando.
- **Coste:** es sensible al coste. Antes de gastar dinero (llamadas de IA para mediciones, servicios de pago), da una
  estimación.
- **Límite de uso:** vigila el límite del plan de la IA que uses. Hacia el 90-95 %, para en un punto limpio:
  - todo probado y subido a la rama;
  - nada a medias en `main` ni en producción;
  - este archivo y el «Pendiente» del README al día.
- **Commits:** en español, estilo `tipo(área): descripción` (`feat`, `fix`, `docs`, `test`, `chore`…), explicando
  el porqué en el cuerpo.
- **Autoría:** el dueño quiere salir como único colaborador en GitHub. Los commits van a su nombre
  (`Álvaro Rovira <281969355+Alvaro-Rovira@users.noreply.github.com>`) y **sin** línea `Co-Authored-By` de la IA.
- **Antes de dar algo por hecho:** pasa todas las pruebas (sección 6). Di lo que no se ha podido probar.

## 3. Reglas de seguridad (no se rompen)

- **Claves y contraseñas nunca por el chat.** El dueño las escribe en el servidor:
  `ssh -t root@161.97.67.178 /opt/kcalia/scripts/set-ai-key.sh VARIABLE`. Admite `ANTHROPIC_API_KEY`,
  `AI_API_KEY`, `AI_VISION_API_KEY`, `BACKUP_REMOTE_ACCESS_KEY`, `BACKUP_REMOTE_SECRET_KEY` y
  `BACKUP_ENCRYPTION_KEY`. La pide sin mostrarla. Abre tú una terminal con ese comando para que la pegue.
- **No leas ni imprimas valores de `/opt/kcalia/.env`.** Para saber si una variable tiene valor:
  `grep -qE '^VAR=.+' .env`. Para cambiar valores que no son secretos: `sed -i`, sin mostrar el fichero.
- **VPS compartida:** en `root@161.97.67.178` hay **otros proyectos en sus propios Docker** (`mosca`, `panel-*`
  con Grafana, Prometheus y Uptime Kuma, `horario-*`, `intradia`, `pokerlog`, `studyflow-*` y `nixai`). **No se
  paran, reinician ni configuran.** Caddy
  está en el host (`/etc/caddy/Caddyfile`); Kcalia solo toca su bloque `# BEGIN/END kcalia` con
  `deploy/caddy-site.sh`, que valida, hace copia y recarga en caliente.
- **Ajustes del sistema de la VPS** (SSH, cortafuegos, fail2ban, reinicios): no los hagas tú. Prepara un script
  (como `deploy/harden-vps.sh`), ábrele una terminal con ssh y que lo lance él.
- **En producción no crees cuentas ni metas contraseñas.** El flujo con sesión se prueba en local (e2e). En
  producción, solo comprobaciones públicas o de solo lectura.
- **Datos del dueño:** solo se tocan cuando él lo pide, siempre con copia previa de la base
  (`sqlite3 .backup` a `backup_dir`).
- **Descargas de terceros:** pide permiso, diciendo qué, de dónde y cuánto ocupa.

## 4. Estado actual (21 de octubre de 2026)

- **Producción:** `main` desplegado en `/opt/kcalia` (el 21 de octubre, con la revisión de seguridad 3).
  Contenedores `kcalia-app` (FastAPI, en `127.0.0.1:8095`) y `kcalia-stt` (Whisper). Base SQLite con migraciones
  por `PRAGMA user_version`, ahora en **v4**. El CI de GitHub va en verde.
- **Ramas:** `main` y `haiku` apuntan al mismo commit. Las ramas `claude/revision-*` son de la sesión de Claude en
  la nube: los PR #1 y #2 ya están fusionados; los #3 (`seguridad`) y #4 (`mejoras-v2`) siguen abiertos, sobre
  ramas antiguas, y no hacen falta (su contenido ya está en `main`).
- **IA:** **Claude Haiku 5.5** (`claude-haiku-5-5`) para texto, fotos, etiquetas y sugerencias, por el SDK oficial
  de Anthropic con salida estructurada. Configuración: `AI_EFFORT=low`. Precios en el panel: 0,10 $ y 0,50 $ por
  millón de tokens. Topes: 60 consultas al día en total y 20 por cuenta. El proveedor anterior se retiró por
  completo (código, configuración, documentación y clave).
- **Precisión medida:**
  - Texto: 30 comidas con cantidades, error medio de 0,7-4,7 % frente a la tabla oficial; ambiguas en rango, 8/10.
  - Fotos: error mediano del 41 % (`app.bench_photos`, 18 platos reales de Nutrition5k); tienden a pasarse con
    raciones pequeñas.
- **Perfil del dueño:** hombre, 167 cm, 65 kg, 20 años en el perfil (él dijo 19), nivel **«medio»**, objetivo
  recomposición. Resultado: 2.280 kcal, 143 g de proteína, 296 g de hidratos y 58 g de grasa (mantenimiento de
  2.342). Días de entreno y descanso desactivados.
- **Seguridad:**
  - Contraseñas con Argon2; sesiones con token guardado como hash y cookie segura.
  - Frenos de login y de confirmación con contraseña; cambio de contraseña desde Ajustes.
  - CSP y cabeceras estrictas; límites de tamaño; imágenes verificadas por sus bytes; CSV sin fórmulas; push solo a
    servicios reales.
  - Fuzzing de las 102 operaciones (`tests/test_fuzz.py`); escrituras simultáneas reintentadas
    (`app/conflicts.py`); `ErrorBoundary` en la web.
  - Detalle en `SECURITY.md` y en el README.
- **VPS:** SSH solo con clave, `MaxAuthTries 3`, fail2ban, ufw con 22/80/443 y actualizaciones automáticas. Kernel
  reiniciado el 15 de octubre.
- **Vigilancia:**
  - Push al administrador por cada error 500, como mucho cada 15 min (`app/notify.py`).
  - Workflow `Disponibilidad` (`.github/workflows/uptime.yml`): abre una incidencia si la web no responde.
  - Comprobación de copias cada lunes (`app/backupcheck.py`).
- **Copias:**
  - Diaria local a las 03:00 (Europe/Madrid), se guardan 7. La comprobación del 16 de octubre: bien.
  - **Copia externa sin configurar**: es lo más urgente del pendiente.

## 5. Mapa del código

```
backend/app/                     FastAPI + SQLAlchemy (Python 3.12, uv)
  main.py                        app, middleware de seguridad, manejador de errores, SPA
  conflicts.py                   reintento de escrituras que chocan en un UNIQUE
  routers/                       API: auth, profile, meals, products, tracking, training, planner, suggest,
                                 summary, weight, account (exportar/borrar/contraseña), importer, push, admin
  ai.py                          cliente de IA: Claude (SDK) o compatible con OpenAI, prompts y esquemas
  foodtable.py, data/            tabla oficial (CIQUAL 2025 + USDA + recetas); fuentes en data/FUENTES.md
  refine.py                      canalización única: la IA identifica y pesa, el código pone valores y aceite
  nutrition.py, daytargets.py    objetivos (niveles de actividad) y días de entreno/descanso (compensados)
  expenditure.py                 gasto real a partir del peso y lo comido
  security.py, deps.py, tenancy.py   contraseñas, sesiones, frenos; acceso; aislamiento por usuario
  jobs.py, offsite.py, backupcheck.py  copias diarias, copia externa cifrada, comprobación semanal
  notify.py, push.py, webpush.py, reminders.py   avisos y recordatorios Web Push
  migrations.py                  migraciones versionadas (v1-v4)
  bench.py, bench_photos.py      mediciones de precisión (texto y fotos)
backend/tests/                   pytest (más de 700 pruebas)
frontend/src/                    React + Vite + TypeScript, PWA, TanStack Query con caché persistida
  pages/                         Today, History, Summary, Weight, Workout, Plan, Settings, Admin, Onboarding, Auth
  offline/                       outbox.ts (cola sin conexión), queryClient.ts (caché), localEdits.ts
  lib/                           lógica pura con tests: dayTargets (espejo de daytargets.py), activity, foods…
  components/ErrorBoundary.tsx   aviso en vez de pantalla en blanco
e2e/                             Playwright: test_flow.py (flujos) y test_zz_extremos.py (datos extremos)
stt/                             servicio de voz (faster-whisper)
deploy/                          deploy.sh, caddy-site.sh, harden-vps.sh
scripts/                         set-ai-key.sh, make-admin.py, restore-backup.py, fetch_nutrition5k.py…
docs/                            DECISIONES.md, PROGRESO*.md, SEGURIDAD-progreso.md, superpowers/ (diseños y planes)
```

Algunas piezas existen dos veces, en Python y en TypeScript, y se prueban con el mismo fichero de casos
(`backend/tests/fixtures/`): la normalización de texto, los objetivos por tipo de día y el emparejado de productos.
**Si cambias una, cambia la otra.**

## 6. Comandos

```bash
# Backend: lint, formato y pruebas
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
# Frontend: tipos, pruebas y build (no hay script de lint)
cd frontend && npx tsc -b && npx vitest run && npm run build
# E2E (desde la raíz; necesitan el build del frontend)
uv run --project backend --group e2e pytest e2e -q
# Desplegar main en la VPS (pull, build, up -d, Caddy y comprobación HTTPS)
./deploy/deploy.sh
# Medir la precisión (en la VPS, con la clave que ya está en el contenedor)
ssh root@161.97.67.178 'cd /opt/kcalia && docker compose exec -T app python -m app.bench --price-in 0.10 --price-out 0.50'
ssh root@161.97.67.178 'cd /opt/kcalia && docker compose run --rm --no-deps -T -v /root/n5k:/n5k:ro app python -m app.bench_photos /n5k --model claude-haiku-5-5 --passes 2'
```

**Antes de desplegar:** pasan ruff, pytest, tsc, vitest, el build y los e2e. Tras desplegar, comprueba
`https://kcalia.space/api/health` y que los demás contenedores siguen arriba (`docker ps`).

## 7. Trampas conocidas

- **iCloud y git:** la carpeta está en el Escritorio de iCloud, y `git checkout` a otra rama crea copias tipo
  `archivo 2.ext`. Trabaja en una rama y avanza `main` sin cambiar de rama: `git update-ref refs/heads/main <rama>`
  (solo si `main` es antecesora), y luego `git push origin main <rama>`.
- **No pases `prettier`:** el proyecto no tiene su configuración y reformatea archivos enteros. El estilo es
  comillas simples, sin punto y coma y líneas largas. Tampoco pases `ruff format` sobre `e2e/`, que va fuera del
  formato del backend.
- **SSH largo sin salida se corta:** usa `-o ServerAliveInterval=30`. Para tareas largas en la VPS:
  `setsid nohup … &`.
- **Variables nuevas:** `deploy.sh` añade a `.env` las que aparezcan en `.env.example` sin tocar las existentes.
- **Fechas:** el «hoy» de la app es Europe/Madrid. Las fechas de entrada se limitan a 1900-2199.
- **Los e2e comparten estado** en orden alfabético: `test_flow.py` crea la cuenta y `test_zz_extremos.py` va al final.

## 8. Historial

- **30 sep 2026 (v1):** primera versión.
  - API con objetivos, historial y resumen semanal; PWA con cuestionario inicial, diario, gráficas, peso y ajustes.
  - Voz con Whisper propio; despliegue en la VPS con Caddy.
  - La IA da valores por 100 g y el código calcula los totales (el modelo escalaba mal).
- **2 oct:** «Mis productos»: foto de la etiqueta, revisión y uso al apuntar comidas.
- **6-7 oct (v2):**
  - Migraciones versionadas, varias cuentas con aprobación y panel de administración.
  - Comidas: ingrediente a mano, copiar comidas y días, favoritos y recientes.
  - Código de barras (Open Food Facts), agua, fibra y alcohol, medidas y fotos de progreso.
  - Entreno: días de entreno y descanso, registro de entrenos y calorías del entreno.
  - Avisos: Web Push y recordatorios.
  - Plan semanal, compra, sugerencias para cerrar el día y compartir la semana como imagen.
  - Copias externas (código), importación desde MyFitnessPal, Yazio y CSV, y atajos de Siri.
  - Dominio **kcalia.space**.
- **14 oct (precisión):**
  - Tabla oficial (472 alimentos y 22 recetas) y canalización única (`refine.py`).
  - Resolución sin IA, gasto real y kcal netas del entreno (Compendium 2024).
  - Resultado: error medio frente a la tabla del 15,8 % → 0,2 %.
  - Arreglos de sincronización y e2e estables en GitHub.
- **15 oct (seguridad 1):**
  - Frenos de login, SSRF en push, límites de tamaño, cabeceras, imágenes por sus bytes y CSV sin fórmulas.
  - `SECURITY.md`; endurecimiento de la VPS (lo aplicó el dueño) y reinicio.
- **16 oct:**
  - **Claude Haiku 5.5** sustituye al proveedor anterior, tras medir texto y fotos; el anterior se retiró de todas
    partes.
  - Revisión del objetivo calórico del dueño:
    - los días de descanso compensan los de entreno;
    - nivel **«Medio» ×1,465**, con los niveles descritos por día y por días de entreno;
    - fotos: «pesa lo que ves» (error mediano del 54 % → 41 %).
  - **Auditoría 2:**
    - fuzzing de la API (500 por identificadores gigantes, fechas extremas y nulos);
    - cambio de contraseña y freno en las confirmaciones;
    - lista de la compra perdida al importar; cola sin conexión con 429/408;
    - concurrencia (500 y comidas perdidas con escrituras simultáneas);
    - pantalla en blanco con una copia local corrupta.
  - **Vigilancia:** avisos de errores 500, aviso de caídas desde GitHub y comprobación semanal de copias.
  - **Registro:** el nivel de actividad sale de dos preguntas (`lib/activity.ts`).
- **17 oct:** este `AGENTS.md` (con `CLAUDE.md` que lo importa) sustituye a `docs/TRASPASO-CODEX.md`.
- **21 oct (revisión de seguridad 3, hecha en una sesión en la nube y desplegada ese mismo día):**
  - una suscripción push con claves rotas cortaba los recordatorios de las demás cuentas;
  - «Borrar mis datos» devolvía el cupo de IA del día (y el global);
  - `null` en los PATCH de ejercicios, entrenos, series y productos daba 500;
  - la importación JSON daba 500 con formas raras y guardaba fechas sin normalizar, que dejaban en 500 las
    estadísticas, el peso y la exportación;
  - certifi, vite y source-map-js actualizados por vulnerabilidades conocidas;
  - `set-ai-key.sh` ya no deja una copia de `.env` en `/tmp` si falla.

Más detalle: `git log` y los documentos de `docs/` (decisiones, progreso de cada etapa y diseños en
`docs/superpowers/`).

## 9. Pendiente

La lista completa, con el diseño de cada punto, está en la sección **«Pendiente» del README**. En resumen:

1. **Copia de seguridad fuera del servidor.** Se eligió Backblaze B2. Falta que el dueño cree la cuenta, el bucket
   privado y una clave limitada a ese bucket, y que dé solo el nombre del bucket y el endpoint. Él mete las tres
   claves con `set-ai-key.sh` (`BACKUP_REMOTE_ACCESS_KEY`, `BACKUP_REMOTE_SECRET_KEY` y `BACKUP_ENCRYPTION_KEY`).
2. **Doble factor (TOTP).** Aprobado y sin empezar; diseño en el README. Obligatorio para el administrador.
3. **Lista de errores y estado de la comprobación de copias en la pantalla del panel** (`Admin.tsx`). La API ya los
   da: `errors` y `backup.check`.
4. **Revocar la clave del proveedor de IA anterior** en su consola. Lo hace el dueño.
5. **Fotos:** se pueden seguir mejorando; si se toca el prompt, hay que validarlo con otra muestra de Nutrition5k.
6. **Exportación:** el JSON exportado no incluye imágenes.
7. **Móvil compartido:** si la sesión caduca y en ese navegador entra otra cuenta, la cola sin conexión de la
   primera se envía a la segunda, y la caché enseña sus datos hasta recargar. Propuesta: al entrar con otro usuario,
   vaciar la cola y la caché (`clearOutbox` y `clearLocalData`).
8. **Cerrar los PR #3 y #4** (revisiones sobre las ramas antiguas `seguridad` y `mejoras-v2`): no se despliegan.
9. **Historial con Claude como colaborador.** Los commits antiguos llevan `Co-Authored-By` de la IA. Quitarlo
   obliga a reescribir el historial: cambian todos los identificadores y hay que rehacer la copia local y la del
   servidor. Sin decidir; si se hace, avisando antes a cualquier otra sesión que trabaje en el proyecto.

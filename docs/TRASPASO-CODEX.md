# Traspaso para Codex (2026-10-16)

Resumen de lo hecho con Claude Code en esta conversación (del 14 al 16 de octubre de 2026) y de lo que queda.
Kcalia es una PWA de calorías y macros: https://kcalia.space · repo `Alvaro-Rovira/kcalia` (público) · carpeta local
`~/Desktop/calculadora gym`. El usuario habla español, es sensible al coste y prefiere autonomía.

## Reglas que hay que respetar

- **Claves de API: nunca por el chat.** El usuario las mete él en el servidor con
  `ssh -t root@161.97.67.178 /opt/kcalia/scripts/set-ai-key.sh [AI_API_KEY|AI_VISION_API_KEY|ANTHROPIC_API_KEY]`
  (las pide sin mostrarlas). No leer ni imprimir `/opt/kcalia/.env` con valores secretos.
- **VPS Contabo `root@161.97.67.178` (Ubuntu 24.04):** hay otros proyectos (`mosca`, `panel-*`, `horario-*`, `nixai`)
  cada uno en su Docker. No pararlos, reiniciarlos ni tocar su configuración. Caddy está en el host
  (`/etc/caddy/Caddyfile`). Kcalia solo gestiona su bloque `# BEGIN/END kcalia`, con `deploy/caddy-site.sh`, que valida,
  hace copia y recarga en caliente. App en `127.0.0.1:8095`.
- **Ajustes de seguridad del sistema** (SSH, ufw, fail2ban): los aplica el usuario. Se le prepara el script y se le
  abre una terminal con ssh para que lo lance.
- **Producción:** no crear cuentas ni meter contraseñas. El flujo con sesión se prueba en local con los e2e.
- **Antes de gastar dinero** (IA de pago, jobs), estimar el coste y avisar.
- **Git en el Mac:** el Escritorio está en iCloud y `git checkout` a otra rama crea copias «archivo 2.ext». Se trabaja
  en una rama y se avanza `main` con `git update-ref refs/heads/main <rama>` cuando main es antecesor (fast-forward),
  sin cambiar de rama.
- **SSH largo sin salida se corta:** usar `-o ServerAliveInterval=30`.

## Estado actual

- **Producción:** desplegado desde `21ebe20`. Contenedores `kcalia-app` y `kcalia-stt`. Base SQLite en
  `user_version` 4. Hay una cuenta (la del usuario, administradora).
- **`main` = rama `haiku`**, igual que producción salvo este documento. `python -m app.bench_photos` ya está en la imagen.
- **Modelos en producción** (`/opt/kcalia/.env`, desde el 2026-10-16, por decisión del usuario): **Claude Haiku 5.5
  para todo**:
  - `AI_MODEL=claude-haiku-5-5`;
  - `AI_VISION_MODEL=`: vacío, así que las fotos también van a Haiku;
  - `AI_EFFORT=low`: mejor en fotos y sin coste en texto;
  - `AI_PRICE_INPUT=0.10` y `AI_PRICE_OUTPUT=0.50`.

  El proveedor anterior se retiró del todo el 2026-10-16 a petición del usuario: su clave se borró del `.env` y de la
  copia de seguridad, y su nombre se quitó del código, la configuración y la documentación. Solo queda Claude, más la
  ruta genérica para proveedores compatibles con OpenAI (sin uso).
- **CI** (GitHub Actions, 4 trabajos): verde en el último commit comprobado (`32319a8`). Las suites locales pasan:
  - pytest: 681;
  - vitest: 200;
  - `tsc` y build;
  - e2e: 27.

## Lo hecho

### 1. Precisión de calorías (desplegado el 14 de octubre)
- **Tabla oficial** en `backend/app/data/`: CIQUAL 2025 + USDA FDC + 22 recetas, 494 entradas.
- **Canalización única** `refine.py`:
  - la IA solo identifica el alimento, la preparación y la cantidad;
  - el código pone los valores por 100 g, calcula los gramos de las unidades y añade el aceite de cocinar según la
    preparación.
- **Otros cambios:**
  - `revalue()` para el historial;
  - gasto real medido (`expenditure.py`);
  - kcal netas de entreno (METs del Compendio 2024);
  - migración v4.
- **Resultado:** el error medio frente a la tabla bajó del 15,8 % al 0,2 %.
- **Documentación:** `docs/PROGRESO-precision.md` y `docs/DECISIONES.md`.

### 2. CI e2e que fallaban solo en GitHub
Hubo cuatro causas, todas arregladas:
- la recarga de datos al arrancar pisaba los cambios locales (se arregló con `offline/localEdits.ts`);
- se podía pulsar «Analizar» antes de que la foto estuviera lista;
- `test_07` esperaba la señal equivocada;
- había selectores `.first` ambiguos.

### 3. Seguridad (desplegado el 15 de octubre)
- **App:**
  - frenos de login por IP y por IP+usuario; el freno por usuario es suave y no bloquea conexiones ya conocidas;
  - push solo a FCM, Mozilla, Apple y Windows (contra SSRF);
  - límite de 1 MiB en JSON y 16 MiB en total, en la app y en Caddy;
  - cabeceras COOP/CORP, Permissions-Policy y HSTS con subdominios;
  - sin cabeceras `Server` ni `Via`;
  - el tipo de imagen se saca de los bytes;
  - los CSV exportados no admiten fórmulas.
- **Tests:** `backend/tests/test_hardening.py`.
- **Documentación:** `SECURITY.md` y `docs/SEGURIDAD-progreso.md`.
- **VPS** (lo aplicó el usuario):
  - `deploy/harden-vps.sh`: `MaxAuthTries 3`, `LoginGraceTime 30`, `X11Forwarding no`, fail2ban;
  - reinicio al kernel 6.8.0-147; los 12 contenedores volvieron solos.

### 4. Objetivo calórico del usuario (revisado, sin tocar código)
- **Perfil:** hombre, 20 años, 167 cm, 65 kg, actividad «moderado», objetivo «recomposición».
- **Cifras:** basal 1.599 kcal; mantenimiento 2.478; base 2.420; entreno +200 → 2.620; descanso −100 → 2.320.
- **Fallo:**
  - Los ajustes de entreno y descanso no se compensan: con 4 días de entreno, la media semanal sale en 2.491 kcal,
    por encima del mantenimiento.
  - Además, «moderado» ya cuenta el gimnasio y los +200 lo vuelven a sumar.
- **Propuesta para el usuario:** actividad «ligero», entreno +150 y descanso −200 → 2.290 / 1.940 kcal.
- **Pendiente en código:** ver «Pendiente», punto 2.

### 5. Claude Haiku 5.5 como proveedor (desplegado el 16 de octubre)
- **Código:**
  - `backend/app/ai.py`: los modelos `claude-...` van por el SDK oficial `anthropic` (1.15).
  - Salida estructurada con esquemas propios del formato que piden los prompts (por 100 g):
    `MEAL_SCHEMA`, `LABEL_SCHEMA`, `PLAN_SCHEMA` y `SUGGEST_SCHEMA`.
  - Fotos como bloque de imagen base64, sin `temperature`.
  - Razonamiento desactivado salvo que se ponga `AI_EFFORT=low|medium|high`.
  - Los errores del SDK se traducen a los `AiError` de siempre.
- **Configuración:** `ANTHROPIC_API_KEY` y `AI_EFFORT` en `config.py` y `.env.example`.
- **Tests:** `backend/tests/test_claude.py`.
- **Banco de texto** (`python -m app.bench`, 40 comidas):
  - sin razonamiento: error medio 4,7 % / 0,7 %, con 29/30 y 30/30 dentro de ±12 %;
  - con `low`: 1,5 % y 29/30;
  - ambiguas en rango: 8/10;
  - latencia: unos 2 s;
  - coste: 0,06 $/100 comidas.
- **Banco de fotos:**
  - Comandos: `scripts/fetch_nutrition5k.py` y `app/bench_photos.py`.
  - Muestra: 20 platos reales pesados de Nutrition5k (Google, CC BY 4.0), en `/root/n5k`, con semilla 2026.
  - Dos excluidos: `dish_1566501594`, cuya etiqueta no incluye la ensalada que se ve, y `dish_1558373159`, que lleva
    un ingrediente «deprecated».
  - Resultado en las 18 verificadas: error mediano de kcal del 68 % sin razonamiento y del 54 % con `low`. Dentro de
    ±30 %: 9/36 y 11/36.
  - Sesgo: se pasa con las raciones pequeñas (de +22 a +32 % en kcal) e infravalora los frutos secos.
  - Resultados en la VPS: `/root/kcalia-bench-*.txt` y `/root/kcalia-fotos-*.txt`.
  - El otro modelo comparado era algo más preciso en fotos (mediana 42 %), pero el usuario eligió Haiku para todo.

## Pendiente

1. **Hecho (2026-10-16):** Haiku 5.5 para todo, con `AI_EFFORT=low`. El proveedor anterior se ha retirado.
2. **Objetivo calórico en código** (lo ofrecí; el usuario aún no ha dicho que sí):
   - Que el ajuste de los días de descanso compense el de los de entreno según el número de días. Está en
     `backend/app/daytargets.py`, su espejo `frontend/src/lib/dayTargets.ts` y los casos compartidos
     `backend/tests/fixtures/day_target_cases.json`.
   - Describir los niveles de actividad por pasos y tipo de trabajo, no por días de gimnasio
     (`frontend/src/lib/options.ts`).
3. **Mejorar las fotos:**
   - Calibrar `PHOTO_INSTRUCTIONS` en `ai.py`: hoy los modelos se pasan con las raciones.
   - Volver a medir con
     `docker compose run --rm --no-deps -T -v /root/n5k:/n5k:ro app python -m app.bench_photos /n5k --model ... --passes 2`.
   - Cuidado: sobreajustarse a 18 platos de cafetería estadounidense.
4. **GitHub:** activar el aviso privado de vulnerabilidades (*Settings → Code security*), al que remite `SECURITY.md`.
   Lo hace el usuario o se hace con `gh api -X PUT repos/Alvaro-Rovira/kcalia/private-vulnerability-reporting` si lo
   autoriza.
5. **Restos del proveedor anterior:**
   - En `/root` de la VPS quedan ficheros de resultados de las pruebas con su nombre: `/root/kcalia-bench-*.txt` y
     `/root/kcalia-fotos-*.txt`. Se borran solo si el usuario lo autoriza.
   - El usuario tiene que revocar la clave en la consola de ese proveedor; en el servidor ya no está.

## Comandos útiles

```bash
cd backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
cd frontend && npx vitest run && npx tsc -b && npm run build
uv run --project backend --group e2e pytest e2e -q            # desde la raíz
./deploy/deploy.sh                                             # pull de main en la VPS, build, up -d y Caddy
ssh root@161.97.67.178 'cd /opt/kcalia && docker compose exec -T app python -m app.bench --price-in 0.10 --price-out 0.50'
```

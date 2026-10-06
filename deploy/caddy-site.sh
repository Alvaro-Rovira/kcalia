#!/usr/bin/env bash
# Añade o actualiza el bloque de Kcalia en el Caddyfile del host, SIN tocar los demás sitios.
#   ./deploy/caddy-site.sh           # aplica (copia, valida y recarga Caddy en caliente)
#   ./deploy/caddy-site.sh --check   # solo enseña el bloque y lo valida, sin cambiar nada
#
# Lee de .env:
#   DOMAIN            dominio principal (HTTPS de Let's Encrypt, renovación automática de Caddy)
#   APP_PORT          puerto local de la app (127.0.0.1)
#   REDIRECT_DOMAINS  otros dominios (www, dominios antiguos) que redirigen con 301 al principal
# HTTP siempre redirige a HTTPS con 301. Para migrar de dominio: cambia DOMAIN, pon el antiguo en REDIRECT_DOMAINS,
# apunta el DNS y vuelve a ejecutarlo.
set -euo pipefail
cd "$(dirname "$0")/.."

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
env_value() { grep -E "^$1=" .env | tail -1 | cut -d= -f2- || true; }
DOMAIN="$(env_value DOMAIN)"
APP_PORT="$(env_value APP_PORT)"
APP_PORT="${APP_PORT:-8095}"
REDIRECT_DOMAINS="$(env_value REDIRECT_DOMAINS)"
[ -n "$DOMAIN" ] || { echo "Falta DOMAIN en .env" >&2; exit 1; }

# El log debe pertenecer al usuario de Caddy: si lo creara `caddy validate` como root, el servicio no podría escribirlo.
if id caddy >/dev/null 2>&1; then
  install -d -o caddy -g caddy /var/log/caddy
  [ -f /var/log/caddy/kcalia.log ] || install -o caddy -g caddy -m 640 /dev/null /var/log/caddy/kcalia.log
fi

candidate="$(mktemp)"
trap 'rm -f "$candidate"' EXIT

DOMAIN="$DOMAIN" APP_PORT="$APP_PORT" REDIRECT_DOMAINS="$REDIRECT_DOMAINS" CADDYFILE="$CADDYFILE" CANDIDATE="$candidate" \
  python3 - <<'PY'
import os, re

domain = os.environ["DOMAIN"].strip()
port = os.environ["APP_PORT"].strip()
others = [d for d in re.split(r"[\s,]+", os.environ["REDIRECT_DOMAINS"]) if d and d != domain]
target = f"https://{domain}{{uri}}"

# Una app instalada desde un dominio antiguo sigue abriéndose desde la caché de su service worker y nunca vería la
# redirección. Este service worker sustituye al antiguo, se da de baja y lleva las ventanas al dominio nuevo.
# Sin llaves: dentro de `respond`, Caddy trataría {...} como variables.
kill_switch = (
    "self.addEventListener('install', () => self.skipWaiting());\n"
    "self.addEventListener('activate', (event) => event.waitUntil(self.registration.unregister()\n"
    "  .then(() => caches.keys()).then((keys) => Promise.all(keys.map((key) => caches.delete(key))))\n"
    "  .then(() => self.clients.matchAll()).then((clients) => clients.forEach((client) => client.navigate(client.url)))));\n"
)

parts = [
    "# BEGIN kcalia (gestionado por deploy/caddy-site.sh)",
    f"""{domain} {{
	encode zstd gzip
	header Strict-Transport-Security "max-age=31536000"
	reverse_proxy 127.0.0.1:{port}
	log {{
		output file /var/log/caddy/kcalia.log
	}}
}}""",
]
if others:
    parts.append(
        f"""{", ".join(others)} {{
	handle /sw.js {{
		header Content-Type "application/javascript; charset=utf-8"
		header Cache-Control "no-cache"
		respond `{kill_switch}` 200
	}}
	handle {{
		redir {target} permanent
	}}
}}"""
    )
plain = ", ".join(f"http://{d}" for d in [domain, *others])
parts.append(
    f"""{plain} {{
	redir {target} permanent
}}"""
)
parts.append("# END kcalia")
block = "\n".join(parts) + "\n"

text = open(os.environ["CADDYFILE"]).read()
pattern = re.compile(r"# BEGIN kcalia.*?# END kcalia\n", re.S)
text = pattern.sub(lambda _: block, text) if pattern.search(text) else text.rstrip("\n") + "\n\n" + block
open(os.environ["CANDIDATE"], "w").write(text)
PY

if [ "$CHECK" = 1 ]; then
  sed -n '/^# BEGIN kcalia/,/^# END kcalia/p' "$candidate"
  if caddy validate --config "$candidate" --adapter caddyfile >/dev/null 2>&1; then
    echo "La configuración valida (no se ha cambiado nada)."
  else
    caddy validate --config "$candidate" --adapter caddyfile >&2 || true
    exit 1
  fi
  exit 0
fi

# Sin cambios no se toca nada: ni copia, ni recarga de Caddy.
if cmp -s "$candidate" "$CADDYFILE"; then
  echo "Caddy ya estaba al día: https://$DOMAIN -> 127.0.0.1:$APP_PORT"
  exit 0
fi

backup="$CADDYFILE.bak-$(date +%Y%m%d%H%M%S)"
cp "$CADDYFILE" "$backup"
cat "$candidate" > "$CADDYFILE"

if caddy validate --config "$CADDYFILE" --adapter caddyfile >/dev/null 2>&1; then
  systemctl reload caddy
  echo "Caddy recargado: https://$DOMAIN -> 127.0.0.1:$APP_PORT${REDIRECT_DOMAINS:+ (redirigen: $REDIRECT_DOMAINS)} (copia en $backup)"
else
  cp "$backup" "$CADDYFILE"
  echo "La configuración de Caddy no valida; restaurada la copia $backup. Salida:" >&2
  caddy validate --config "$CADDYFILE" --adapter caddyfile >&2 || true
  exit 1
fi

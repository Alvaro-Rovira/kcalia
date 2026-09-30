#!/usr/bin/env bash
# Añade o actualiza el bloque de Kcalia en el Caddyfile del host, SIN tocar los demás sitios.
# Lee DOMAIN y APP_PORT de .env. Para migrar de dominio: cambia DOMAIN, apunta el DNS y vuelve a ejecutarlo.
# Hace copia del Caddyfile, valida y solo entonces recarga (sin cortar el resto de sitios).
set -euo pipefail
cd "$(dirname "$0")/.."

CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
DOMAIN="$(grep -E '^DOMAIN=' .env | tail -1 | cut -d= -f2-)"
APP_PORT="$(grep -E '^APP_PORT=' .env | tail -1 | cut -d= -f2- || true)"
APP_PORT="${APP_PORT:-8095}"
[ -n "$DOMAIN" ] || { echo "Falta DOMAIN en .env" >&2; exit 1; }

# El log debe pertenecer al usuario de Caddy: si lo creara `caddy validate` como root, el servicio no podría escribirlo.
if id caddy >/dev/null 2>&1; then
  install -d -o caddy -g caddy /var/log/caddy
  [ -f /var/log/caddy/kcalia.log ] || install -o caddy -g caddy -m 640 /dev/null /var/log/caddy/kcalia.log
fi

candidate="$(mktemp)"
trap 'rm -f "$candidate"' EXIT

DOMAIN="$DOMAIN" APP_PORT="$APP_PORT" CADDYFILE="$CADDYFILE" CANDIDATE="$candidate" python3 - <<'PY'
import os, re
block = f"""# BEGIN kcalia (gestionado por deploy/caddy-site.sh)
{os.environ["DOMAIN"]} {{
	encode zstd gzip
	header Strict-Transport-Security "max-age=31536000"
	reverse_proxy 127.0.0.1:{os.environ["APP_PORT"]}
	log {{
		output file /var/log/caddy/kcalia.log
	}}
}}
# END kcalia
"""
text = open(os.environ["CADDYFILE"]).read()
pattern = re.compile(r"# BEGIN kcalia.*?# END kcalia\n", re.S)
text = pattern.sub(lambda _: block, text) if pattern.search(text) else text.rstrip("\n") + "\n\n" + block
open(os.environ["CANDIDATE"], "w").write(text)
PY

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
  echo "Caddy recargado: https://$DOMAIN -> 127.0.0.1:$APP_PORT (copia en $backup)"
else
  cp "$backup" "$CADDYFILE"
  echo "La configuración de Caddy no valida; restaurada la copia $backup. Salida:" >&2
  caddy validate --config "$CADDYFILE" --adapter caddyfile >&2 || true
  exit 1
fi

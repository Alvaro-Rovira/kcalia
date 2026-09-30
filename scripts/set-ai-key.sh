#!/usr/bin/env bash
# Guarda la clave de la IA en .env sin mostrarla ni dejarla en el historial ni en la lista de procesos.
#   ssh -t root@TU_VPS /opt/kcalia/scripts/set-ai-key.sh
# Después: cd /opt/kcalia && docker compose up -d app
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "No existe .env en $(pwd)" >&2; exit 1; }

read -rs -p "Clave de la API de IA (no se mostrará): " KEY
echo
[ -n "$KEY" ] || { echo "No has escrito nada; no se cambia nada." >&2; exit 1; }

tmp="$(mktemp)"
# La clave viaja por el entorno de awk, no por argumentos, y no se interpreta (sin escapes ni comodines).
KEY="$KEY" awk '
  /^AI_API_KEY=/ { print "AI_API_KEY=" ENVIRON["KEY"]; done = 1; next }
  { print }
  END { if (!done) print "AI_API_KEY=" ENVIRON["KEY"] }
' .env > "$tmp"
cat "$tmp" > .env
rm -f "$tmp"
chmod 600 .env
unset KEY
echo "Clave guardada en $(pwd)/.env (permisos 600)."
echo "Aplícala con:  cd $(pwd) && docker compose up -d app"

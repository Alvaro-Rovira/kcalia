#!/usr/bin/env bash
# Guarda la clave de la IA en .env sin mostrarla ni dejarla en el historial ni en la lista de procesos.
#   ssh -t root@TU_VPS /opt/kcalia/scripts/set-ai-key.sh                     # AI_API_KEY (proveedor compatible con OpenAI)
#   ssh -t root@TU_VPS /opt/kcalia/scripts/set-ai-key.sh ANTHROPIC_API_KEY   # clave de Claude (la habitual)
# Después: cd /opt/kcalia && docker compose up -d app
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "No existe .env en $(pwd)" >&2; exit 1; }

VAR="${1:-AI_API_KEY}"
case "$VAR" in
  AI_API_KEY | AI_VISION_API_KEY | ANTHROPIC_API_KEY) ;;
  *) echo "Variable no admitida: $VAR (AI_API_KEY, AI_VISION_API_KEY o ANTHROPIC_API_KEY)" >&2; exit 1 ;;
esac

read -rs -p "Clave para $VAR (no se mostrará): " KEY
echo
[ -n "$KEY" ] || { echo "No has escrito nada; no se cambia nada." >&2; exit 1; }

tmp="$(mktemp)"
# La clave viaja por el entorno de awk, no por argumentos, y no se interpreta (sin escapes ni comodines).
KEY="$KEY" VAR="$VAR" awk '
  index($0, ENVIRON["VAR"] "=") == 1 { print ENVIRON["VAR"] "=" ENVIRON["KEY"]; done = 1; next }
  { print }
  END { if (!done) print ENVIRON["VAR"] "=" ENVIRON["KEY"] }
' .env > "$tmp"
cat "$tmp" > .env
rm -f "$tmp"
chmod 600 .env
unset KEY
echo "$VAR guardada en $(pwd)/.env (permisos 600)."
echo "Aplícala con:  cd $(pwd) && docker compose up -d app"

#!/usr/bin/env bash
# Despliega la última versión de main en la VPS y comprueba que responde por HTTPS.
#   ./deploy/deploy.sh                 # usa los valores por defecto
#   DEPLOY_HOST=root@1.2.3.4 ./deploy/deploy.sh
set -euo pipefail

HOST="${DEPLOY_HOST:-root@161.97.67.178}"
DIR="${DEPLOY_DIR:-/opt/kcalia}"
REPO="${DEPLOY_REPO:-https://github.com/Alvaro-Rovira/kcalia.git}"

echo "==> Actualizando código y contenedores en $HOST"
ssh "$HOST" bash -s <<REMOTE
set -euo pipefail
[ -d "$DIR/.git" ] || git clone "$REPO" "$DIR"
cd "$DIR"
git pull --ff-only
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Creado .env a partir de .env.example: falta poner la clave con scripts/set-ai-key.sh"
fi
docker compose up -d --build
chmod +x deploy/*.sh scripts/*.sh
./deploy/caddy-site.sh
REMOTE

DOMAIN="$(ssh "$HOST" "grep -E '^DOMAIN=' $DIR/.env | cut -d= -f2-")"
echo "==> Comprobando https://$DOMAIN"
for i in $(seq 1 30); do
  if curl -fsS "https://$DOMAIN/api/health" >/dev/null 2>&1; then
    echo "OK: https://$DOMAIN responde"
    exit 0
  fi
  sleep 3
done
echo "No responde tras 90 s. Revisa: ssh $HOST 'cd $DIR && docker compose logs --tail=50'" >&2
exit 1

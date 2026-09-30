.PHONY: help dev test test-api test-web test-voz e2e build assets deploy

help:            ## Lista los comandos
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-9s %s\n", $$1, $$2}'

dev:             ## API (8765) con IA simulada + frontend con recarga en caliente (5173)
	@echo "Terminal 1: uv run --project backend python e2e/fake_ai.py --port 8799"
	@echo "Terminal 2: cd backend && AI_BASE_URL=http://127.0.0.1:8799/v1 AI_API_KEY=x COOKIE_SECURE=false uv run uvicorn app.main:app --port 8765"
	@echo "Terminal 3: cd frontend && npm run dev"

test: test-api test-web test-voz  ## Tests unitarios (API, frontend y voz)

test-api:        ## Cálculos, normalización, coincidencias, resumen y API
	cd backend && uv run pytest -q

test-web:        ## Formato, fechas y espejo de la normalización
	cd frontend && npm test

test-voz:        ## Decodificación de audio de cada navegador
	cd stt && uv run --python 3.12 --with-requirements requirements.txt --with pytest pytest -q test_audio.py

build:           ## Compila el frontend
	cd frontend && npm ci && npm run build

e2e: build       ## Flujo completo en un navegador (móvil de 390 px)
	uv run --project backend --group e2e python -m playwright install chromium
	uv run --project backend --group e2e pytest e2e -q

assets:          ## Regenera iconos, splash e imagen social
	uv run --with playwright python scripts/generate_assets.py

deploy:          ## Despliega en la VPS (ver deploy/deploy.sh)
	./deploy/deploy.sh

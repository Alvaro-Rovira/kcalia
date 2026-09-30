# syntax=docker/dockerfile:1.7

# ---- 1. Frontend -------------------------------------------------------------
FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. Dependencias de Python -----------------------------------------------
FROM python:3.12-slim AS deps
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
RUN pip install --no-cache-dir uv==0.12.17
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- 3. Imagen final ---------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/data BACKUP_DIR=/backups STATIC_DIR=/app/static
RUN useradd --system --uid 10001 --no-create-home kcalia \
    && mkdir -p /data /backups && chown kcalia /data /backups
WORKDIR /app
COPY --from=deps /app/.venv /app/.venv
COPY backend/app ./app
COPY --from=web /web/dist ./static
USER kcalia
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
# Detrás de Caddy: se confía en X-Forwarded-For para ver la IP real (el puerto solo escucha en loopback).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--log-level", "warning"]

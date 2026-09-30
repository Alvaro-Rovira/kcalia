"""Arranca la IA simulada y la app real (API + frontend compilado) con datos temporales."""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "frontend" / "dist"
PASSWORD = "clave-de-prueba-1"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(url: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=1).status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(0.2)
    raise RuntimeError(f"No arranca {url}")


@pytest.fixture(scope="session")
def servers():
    if not (DIST / "index.html").exists():
        pytest.skip("Falta el frontend compilado: cd frontend && npm run build")
    ai_port, app_port = free_port(), free_port()
    data = Path(tempfile.mkdtemp(prefix="kcalia-e2e-"))
    env = {
        **os.environ,
        "DATA_DIR": str(data),
        "BACKUP_DIR": str(data / "backups"),
        "STATIC_DIR": str(DIST),
        "COOKIE_SECURE": "false",
        "AI_BASE_URL": f"http://127.0.0.1:{ai_port}/v1",
        "AI_API_KEY": "fake",
        "STT_BASE_URL": f"http://127.0.0.1:{ai_port}/v1",
        "AI_DAILY_LIMIT": "50",
        "TZ": "Europe/Madrid",
    }
    backend = ROOT / "backend"
    procs = [
        subprocess.Popen([sys.executable, str(ROOT / "e2e" / "fake_ai.py"), "--port", str(ai_port)], env=env),
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(app_port), "--log-level", "warning"],
            cwd=backend,
            env=env,
        ),
    ]
    try:
        wait_for(f"http://127.0.0.1:{ai_port}/calls")
        wait_for(f"http://127.0.0.1:{app_port}/api/health")
        yield {"app": f"http://127.0.0.1:{app_port}", "ai": f"http://127.0.0.1:{ai_port}"}
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=10)


@pytest.fixture(scope="session")
def browser_instance():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture()
def ai_calls(servers):
    def read() -> int:
        return httpx.get(f"{servers['ai']}/calls").json()["chat"]

    return read

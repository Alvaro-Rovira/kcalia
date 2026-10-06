import logging
import threading
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import tenancy  # noqa: F401  (registra el filtro por usuario en las sesiones)
from .ai import AiError
from .config import get_settings
from .db import init_db
from .deps import enforce_access
from .jobs import start_scheduler
from .routers import account, admin, auth, meals, products, profile, summary, tracking, weight
from .spa import render_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kcalia")

CSP = (
    "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
    # wasm-unsafe-eval: solo permite compilar WebAssembly (el lector de códigos de barras de respaldo).
    "style-src 'self' 'unsafe-inline'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'; "
    "font-src 'self'; worker-src 'self'; manifest-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(self), microphone=(self), geolocation=()",
    "X-Frame-Options": "DENY",
}
# Ficheros que no deben quedarse en caché: de ellos depende que llegue una versión nueva.
NO_CACHE_FILES = {"index.html", "sw.js", "registerSW.js", "manifest.webmanifest"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    stop = threading.Event()
    start_scheduler(stop)
    yield
    stop.set()


# enforce_access se aplica a TODAS las rutas: lo que no sea público exige una cuenta aprobada.
app = FastAPI(
    title="Kcalia",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    dependencies=[Depends(enforce_access)],
)


if get_settings().gzip:
    app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def security(request: Request, call_next):
    # Una petición que modifica datos desde otro origen no es nuestra app.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Origen no permitido."}, status_code=403)
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(AiError)
async def ai_error(_: Request, exc: AiError):
    return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=exc.status)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(
            {"detail": exc.detail.get("message", ""), "code": exc.detail.get("code")}, status_code=exc.status_code
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    fields = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc")})
    hint = f" ({', '.join(fields)})" if fields else ""
    return JSONResponse({"detail": f"Hay algún dato que no cuadra{hint}. Revísalo y prueba otra vez."}, status_code=422)


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception):
    log.exception("Error no controlado", exc_info=exc)
    return JSONResponse(
        {"detail": "Algo ha fallado por nuestra parte. Inténtalo de nuevo en un momento."}, status_code=500
    )


@app.api_route("/api/health", methods=["GET", "HEAD"])
def health() -> dict:
    return {"status": "ok"}


for module in (auth, profile, meals, products, weight, summary, tracking, account, admin):
    app.include_router(module.router)


@app.api_route("/api/{rest:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_not_found(rest: str):
    raise HTTPException(404, "Esa ruta de la API no existe.")


def _mount_frontend() -> None:
    static_dir = get_settings().static_dir.resolve()
    index = static_dir / "index.html"
    if not index.exists():
        log.warning("No hay frontend compilado en %s: solo se sirve la API", static_dir)
        return

    # Las metas Open Graph necesitan URL absoluta: se rellenan con DOMAIN, el único sitio donde vive el dominio.
    settings = get_settings()
    origin = "" if settings.domain in ("", "localhost") else f"https://{settings.domain}"
    rendered = render_index(static_dir, origin)
    index_headers = {"Cache-Control": "no-cache"}
    if rendered.script_hash:
        index_headers["Content-Security-Policy"] = CSP.replace(
            "script-src 'self'", f"script-src 'self' '{rendered.script_hash}'"
        )

    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.middleware("http")
    async def cache_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    # HEAD también: monitores y `curl -I` lo usan.
    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str):
        candidate = (static_dir / path).resolve()
        if path and path != "index.html" and candidate.is_file() and static_dir in candidate.parents:
            headers = (
                {"Cache-Control": "no-cache"}
                if candidate.name in NO_CACHE_FILES
                else {"Cache-Control": "public, max-age=86400"}
            )
            return FileResponse(candidate, headers=headers)
        # Cualquier otra ruta es de la SPA: el router del cliente decide (incluida la 404).
        return HTMLResponse(rendered.html, headers=index_headers)


_mount_frontend()

"""Prepara el index.html de la SPA para servirlo: dominio real en las metas y recursos críticos en línea."""

import base64
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_THEME_TAG = '<script src="/theme.js"></script>'
_CSS_LINK = re.compile(r'<link\b[^>]*rel="stylesheet"[^>]*href="(/assets/[^"]+\.css)"[^>]*>')
_FONT_FILE = re.compile(r"geist-latin-wght-normal-[\w-]+\.woff2$")


@dataclass(frozen=True)
class RenderedIndex:
    html: str
    # Hash (CSP) del script del tema una vez puesto en línea; None si no se ha puesto.
    script_hash: str | None


def render_index(static_dir: Path, origin: str) -> RenderedIndex:
    """El HTML es lo primero que llega: con el tema y el CSS dentro, el primer pintado no espera más
    viajes a la red. El script del tema va con hash en la CSP, sin abrir 'unsafe-inline' para scripts."""
    html = (static_dir / "index.html").read_text().replace("__ORIGIN__", origin)

    for link in _CSS_LINK.finditer(html):
        css_file = static_dir / link.group(1).lstrip("/")
        if css_file.is_file():
            html = html.replace(link.group(0), f"<style>{css_file.read_text()}</style>")

    script_hash = None
    theme = static_dir / "theme.js"
    if _THEME_TAG in html and theme.is_file():
        code = theme.read_text()
        html = html.replace(_THEME_TAG, f"<script>{code}</script>")
        script_hash = "sha256-" + base64.b64encode(hashlib.sha256(code.encode()).digest()).decode()

    fonts = (
        sorted((static_dir / "assets").glob("geist-latin-wght-normal-*.woff2"))
        if (static_dir / "assets").is_dir()
        else []
    )
    if fonts and _FONT_FILE.search(fonts[0].name):
        preload = f'<link rel="preload" href="/assets/{fonts[0].name}" as="font" type="font/woff2" crossorigin />'
        html = html.replace("</head>", f"    {preload}\n  </head>", 1)
    return RenderedIndex(html, script_hash)

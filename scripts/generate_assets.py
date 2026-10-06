"""Genera los activos gráficos de la PWA (iconos, favicon, splash de iOS y Open Graph).

    uv run --with playwright python scripts/generate_assets.py            # todo
    uv run --with playwright python scripts/generate_assets.py --atajos   # solo los iconos de los atajos

Renderiza el isotipo con un navegador headless, así que salen nítidos a cualquier tamaño y con
la tipografía real de la app. Los resultados se guardan en frontend/public y se versionan.
"""

import re
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "frontend" / "public"
FONT = ROOT / "frontend" / "node_modules" / "@fontsource-variable" / "geist" / "files" / "geist-latin-wght-normal.woff2"

BG = "#0b0c0e"
TRACK = "rgba(255,255,255,0.10)"
INK = "#f4f5f7"
ACCENT = "#34d399"
ACCENT_TEXT = "#4ade9f"
ORANGE = "#ff8a3d"

# Vista de 64×64: anillo de progreso (naranja -> esmeralda) con una "k" dentro.
LOGO_PATHS = """
  <circle cx="32" cy="32" r="24" fill="none" stroke="{track}" stroke-width="7"/>
  <circle cx="32" cy="32" r="24" fill="none" stroke="url(#g)" stroke-width="7" stroke-linecap="round"
          stroke-dasharray="116 151" transform="rotate(-90 32 32)"/>
  <path d="M27 22v20M27 34l9-8M30.5 31.5 37 42" fill="none" stroke="{ink}" stroke-width="4.2"
        stroke-linecap="round" stroke-linejoin="round"/>
"""
GRADIENT = f'<linearGradient id="g" x1="12%" y1="88%" x2="88%" y2="12%"><stop offset="0%" stop-color="{ORANGE}"/><stop offset="100%" stop-color="{ACCENT}"/></linearGradient>'


def logo_svg(size: float, x: float = 0, y: float = 0) -> str:
    return (
        f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 64 64">'
        f"<defs>{GRADIENT}</defs>{LOGO_PATHS.format(track=TRACK, ink=INK)}</svg>"
    )


def page(width: int, height: int, body: str, extra_css: str = "") -> str:
    return f"""<!doctype html><meta charset="utf-8">
<style>
@font-face {{ font-family: Geist; src: url('{FONT.as_uri()}') format('woff2-variations'); font-weight: 100 900; }}
html, body {{ margin: 0; width: {width}px; height: {height}px; background: transparent; overflow: hidden; }}
{extra_css}
</style>{body}"""


def icon_html(size: int, *, maskable: bool, scale: float | None = None) -> str:
    # Maskable: sin esquinas redondeadas (el sistema aplica su máscara) y logo dentro de la zona segura.
    box = size * (scale if scale else 0.62 if maskable else 0.70)
    offset = (size - box) / 2
    radius = 0 if maskable else size * 0.225
    body = f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
  <defs><radialGradient id="glow" cx="50%" cy="42%" r="60%"><stop offset="0%" stop-color="{ACCENT}" stop-opacity="0.16"/><stop offset="100%" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient></defs>
  <rect width="{size}" height="{size}" rx="{radius}" fill="{BG}"/>
  <rect width="{size}" height="{size}" rx="{radius}" fill="url(#glow)"/>
  {logo_svg(box, offset, offset)}
</svg>"""
    return page(size, size, body)


# Glifos de Lucide (ISC) en una vista de 24×24 para los iconos de los atajos de la PWA.
SHORTCUTS = {
    "shortcut-add": (ACCENT, ["M5 12h14", "M12 5v14"]),
    "shortcut-water": (
        "#6cb6ff",
        ["M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"],
    ),
    "shortcut-workout": (
        ORANGE,
        [
            "M17.596 12.768a2 2 0 1 0 2.829-2.829l-1.768-1.767a2 2 0 0 0 2.828-2.829l-2.828-2.828a2 2 0 0 0-2.829 2.828"
            "l-1.767-1.768a2 2 0 1 0-2.829 2.829z",
            "m2.5 21.5 1.4-1.4",
            "m20.1 3.9 1.4-1.4",
            "M5.343 21.485a2 2 0 1 0 2.829-2.828l1.767 1.768a2 2 0 1 0 2.829-2.829l-6.364-6.364a2 2 0 1 0-2.829 2.829"
            "l1.768 1.767a2 2 0 0 0-2.828 2.829z",
            "m9.6 14.4 4.8-4.8",
        ],
    ),
    "shortcut-weight": (
        "#7f95ff",
        [
            "M12 3v18",
            "m19 8 3 8a5 5 0 0 1-6 0zV7",
            "M3 7h1a17 17 0 0 0 8-2 17 17 0 0 0 8 2h1",
            "m5 8 3 8a5 5 0 0 1-6 0zV7",
            "M7 21h10",
        ],
    ),
}


def shortcut_html(size: int, color: str, paths: list[str]) -> str:
    """Icono de atajo: fondo de la app y el glifo de la acción en su color (Android lo recorta en círculo)."""
    glyph = size * 0.5
    offset = (size - glyph) / 2
    strokes = "".join(f'<path d="{d}"/>' for d in paths)
    body = f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{size}" height="{size}" rx="{size / 2}" fill="{BG}"/>
  <svg x="{offset}" y="{offset}" width="{glyph}" height="{glyph}" viewBox="0 0 24 24" fill="none" stroke="{color}"
       stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{strokes}</svg>
</svg>"""
    return page(size, size, body)


def opaque_icon_html(size: int) -> str:
    """Apple Touch Icon: cuadrada y opaca; iOS pone las esquinas."""
    return icon_html(size, maskable=True, scale=0.70)


def splash_html(width: int, height: int) -> str:
    unit = min(width, height)
    box = unit * 0.24
    wordmark = unit * 0.075
    body = f"""<div style="position:relative;width:{width}px;height:{height}px;background:
      radial-gradient(120% 60% at 50% -10%, rgba(52,211,153,0.10), transparent 60%), {BG};
      display:flex;flex-direction:column;align-items:center;justify-content:center;gap:{unit * 0.035}px">
  <svg width="{box}" height="{box}" viewBox="0 0 64 64"><defs>{GRADIENT}</defs>{LOGO_PATHS.format(track=TRACK, ink=INK)}</svg>
  <div style="font-family:Geist;font-weight:600;font-size:{wordmark}px;letter-spacing:-0.035em;color:{INK}"><span style="color:{ACCENT_TEXT}">k</span>calia</div>
</div>"""
    return page(width, height, body)


def og_html() -> str:
    body = f"""<div style="position:relative;width:1200px;height:630px;background:
      radial-gradient(90% 90% at 85% 10%, rgba(52,211,153,0.16), transparent 60%), {BG};
      display:flex;align-items:center;padding:0 96px;gap:72px;font-family:Geist;color:{INK}">
  <svg width="300" height="300" viewBox="0 0 64 64" style="flex:none"><defs>{GRADIENT}</defs>{LOGO_PATHS.format(track=TRACK, ink=INK)}</svg>
  <div>
    <div style="font-weight:600;font-size:132px;letter-spacing:-0.045em;line-height:1"><span style="color:{ACCENT_TEXT}">k</span>calia</div>
    <div style="margin-top:22px;font-size:44px;font-weight:500;letter-spacing:-0.02em;color:#aab0bb;line-height:1.2">Calorías y macros, con calma.</div>
    <div style="margin-top:34px;display:flex;gap:14px">
      <span style="padding:10px 22px;border-radius:99px;background:rgba(127,149,255,0.16);color:#9aacff;font-size:26px;font-weight:600">P Proteínas</span>
      <span style="padding:10px 22px;border-radius:99px;background:rgba(246,196,69,0.15);color:#f6c445;font-size:26px;font-weight:600">H Hidratos</span>
      <span style="padding:10px 22px;border-radius:99px;background:rgba(238,107,176,0.16);color:#f58fc4;font-size:26px;font-weight:600">G Grasas</span>
    </div>
  </div>
</div>"""
    return page(1200, 630, body)


def favicon_svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>{GRADIENT}</defs>
  <rect width="64" height="64" rx="15" fill="{BG}"/>
  <g transform="translate(6.4 6.4) scale(0.8)">{LOGO_PATHS.format(track=TRACK, ink=INK)}</g>
</svg>
"""


# (ancho, alto, píxeles por punto) de iPhone y iPad en vertical, en píxeles físicos.
SPLASH = [
    (1320, 2868, 3), (1206, 2622, 3), (1290, 2796, 3), (1179, 2556, 3), (1284, 2778, 3), (1170, 2532, 3),
    (1125, 2436, 3), (1242, 2688, 3), (828, 1792, 2), (1242, 2208, 3), (750, 1334, 2),
    (1620, 2160, 2), (1668, 2224, 2), (1640, 2360, 2), (1668, 2388, 2), (2048, 2732, 2),
]


def main(only_shortcuts: bool = False) -> None:
    (PUBLIC / "icons").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "splash").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "favicon.svg").write_text(favicon_svg())
    tmp = Path(tempfile.mkdtemp(prefix="kcalia-assets-"))

    def render(browser, html: str, width: int, height: int, target: Path, transparent: bool = False) -> None:
        file = tmp / "asset.html"
        file.write_text(html)
        context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
        tab = context.new_page()
        tab.goto(file.as_uri())
        tab.evaluate("document.fonts.ready")
        tab.wait_for_timeout(120)
        tab.screenshot(path=str(target), omit_background=transparent, clip={"x": 0, "y": 0, "width": width, "height": height})
        context.close()
        print("·", target.relative_to(ROOT))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, (color, paths) in SHORTCUTS.items():
            render(browser, shortcut_html(96, color, paths), 96, 96, PUBLIC / "icons" / f"{name}.png", transparent=True)
        if only_shortcuts:
            browser.close()
            return
        for size in (192, 512):
            render(browser, icon_html(size, maskable=False), size, size, PUBLIC / "icons" / f"icon-{size}.png", transparent=True)
            render(browser, icon_html(size, maskable=True), size, size, PUBLIC / "icons" / f"maskable-{size}.png")
        render(browser, opaque_icon_html(180), 180, 180, PUBLIC / "apple-touch-icon.png")
        render(browser, icon_html(32, maskable=False), 32, 32, PUBLIC / "favicon-32.png", transparent=True)
        render(browser, og_html(), 1200, 630, PUBLIC / "og-image.png")
        links = []
        for width, height, ratio in SPLASH:
            name = f"splash-{width}x{height}.png"
            render(browser, splash_html(width, height), width, height, PUBLIC / "splash" / name)
            css_w, css_h = width // ratio, height // ratio
            media = f"(device-width: {css_w}px) and (device-height: {css_h}px) and (-webkit-device-pixel-ratio: {ratio}) and (orientation: portrait)"
            links.append(f'    <link rel="apple-touch-startup-image" media="{media}" href="/splash/{name}" />')
        browser.close()

    # Los enlaces de splash se inyectan entre los marcadores de index.html.
    index = ROOT / "frontend" / "index.html"
    html = index.read_text()
    block = "<!-- splash:start -->\n" + "\n".join(links) + "\n    <!-- splash:end -->"
    html = re.sub(r"<!-- splash:start -->.*?<!-- splash:end -->", block, html, flags=re.S)
    index.write_text(html)
    print(f"· {len(links)} enlaces de splash en frontend/index.html")


if __name__ == "__main__":
    import sys

    main(only_shortcuts="--atajos" in sys.argv)

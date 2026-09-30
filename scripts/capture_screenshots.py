"""Genera las capturas y el GIF del README a partir de la app real.

    cd frontend && npm run build
    uv run --project backend --group e2e --with pillow python scripts/capture_screenshots.py

Levanta la app con una IA simulada (e2e/fake_ai.py) y datos temporales, hace el onboarding
por la interfaz, siembra un par de semanas de actividad a través de la propia API y captura
en un móvil de 390 px, en oscuro y en claro. Los datos de las capturas son de demostración
y no salen de esta máquina: nada de esto se usa en producción.
"""

import os
import random
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "e2e"))

from conftest import DIST, free_port, wait_for  # noqa: E402
from playwright.sync_api import Page, sync_playwright  # noqa: E402

OUT = ROOT / "docs" / "screenshots"
PASSWORD = "demo-password-1"
MOBILE = {"width": 390, "height": 844}

# Comidas de la despensa de demostración: la IA simulada las conoce por palabras clave.
POOL = {
    "desayuno": ["avena con plátano y leche", "dos huevos revueltos con una tostada de pan integral y aceite", "café con leche"],
    "comida": ["pechuga de pollo con arroz", "lentejas con chorizo", "pasta con tomate y carne", "salmón con patata y brócoli"],
    "merienda": ["yogur griego con nueces", "batido de proteína"],
    "cena": ["salmón con patata y brócoli", "pechuga de pollo con arroz", "pasta con tomate y carne"],
}


def start_servers() -> tuple[dict, list[subprocess.Popen], Path]:
    ai_port, app_port = free_port(), free_port()
    data = Path(tempfile.mkdtemp(prefix="kcalia-shots-"))
    env = {
        **os.environ,
        "DATA_DIR": str(data),
        "BACKUP_DIR": str(data / "backups"),
        "STATIC_DIR": str(DIST),
        "COOKIE_SECURE": "false",
        "AI_BASE_URL": f"http://127.0.0.1:{ai_port}/v1",
        "AI_API_KEY": "demo",
        "STT_BASE_URL": f"http://127.0.0.1:{ai_port}/v1",
        "AI_DAILY_LIMIT": "200",
        "TZ": "Europe/Madrid",
        "FAKE_AI_DELAY": "1.6",
    }
    procs = [
        subprocess.Popen([sys.executable, str(ROOT / "e2e" / "fake_ai.py"), "--port", str(ai_port)], env=env),
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(app_port), "--log-level", "warning"],
            cwd=ROOT / "backend",
            env=env,
        ),
    ]
    wait_for(f"http://127.0.0.1:{ai_port}/calls")
    wait_for(f"http://127.0.0.1:{app_port}/api/health")
    return {"app": f"http://127.0.0.1:{app_port}"}, procs, data


def onboard(page: Page, base: str, out: Path) -> None:
    """Registro y onboarding por la interfaz; de paso captura la pantalla del plan."""
    page.goto(base)
    page.locator("input[name=username]").fill("demo")
    page.locator("input[name=password]").fill(PASSWORD)
    page.get_by_role("button", name="Crear cuenta").click()
    page.get_by_role("button", name="Empezar", exact=True).click()
    page.get_by_role("radio", name="Hombre").click()
    page.get_by_role("button", name="Continuar").click()  # edad
    page.get_by_role("button", name="Continuar").click()  # peso
    page.get_by_role("button", name="Continuar").click()  # altura
    page.get_by_role("radio", name=" Moderado").click()
    page.get_by_role("radio", name="Definición ligera").click()
    page.get_by_role("button", name="Saltar").click()
    page.get_by_text("Cómo lo he calculado").wait_for()
    page.wait_for_timeout(2200)
    page.screenshot(path=str(out / "08-plan.png"))
    page.get_by_role("button", name="Empezar con este plan").click()
    page.get_by_text("Aún no has apuntado nada").wait_for()


def seed(page: Page, base: str) -> None:
    """Dos semanas creíbles: casi todos los días cerca del objetivo, algún fallo y una racha en curso."""
    rq = page.request
    random.seed(11)
    targets = rq.get(f"{base}/api/bootstrap").json()["targets"]
    today = date.today()
    known: dict[str, dict] = {}

    def resolve(text: str) -> dict:
        reply = rq.post(f"{base}/api/meals/resolve", data={"text": text}).json()
        return reply["draft"] if "draft" in reply else reply["candidates"][0]

    def add(day: date, slot: str, text: str, servings: float) -> float:
        draft = resolve(text)
        source = draft["source"] if draft["source"] in ("exact", "fuzzy") else "ai"
        body = {
            "client_id": str(uuid.uuid4()),
            "date": day.isoformat(),
            "slot": slot,
            "name": draft["name"],
            "text": text,
            "items": draft["items"],
            "servings": servings,
            "source": source,
            "via": "text",
            "confidence": draft["confidence"],
            "assumptions": draft["assumptions"],
            "dish_id": draft.get("dish_id"),
        }
        assert rq.post(f"{base}/api/meals", data=body).status == 201
        known[text] = draft
        return draft["kcal"] * servings

    def fill_day(day: date, share: float, slots: tuple[str, ...]) -> None:
        picks = [(slot, random.choice(POOL[slot])) for slot in slots]
        base_kcal = sum(resolve(text)["kcal"] for _, text in picks)
        scale = targets["kcal"] * share / base_kcal
        for slot, text in picks:
            add(day, slot, text, max(0.5, round(scale * 4) / 4))

    all_slots = ("desayuno", "comida", "merienda", "cena")
    plan = {13: 1.0, 12: 0.97, 11: 1.02, 10: 0.96, 9: 1.32, 8: 0.99, 7: 1.04, 6: None, 5: 1.0, 4: 0.94, 3: 0.72, 2: 1.03, 1: 0.98}
    for back in range(13, 0, -1):
        share = plan[back]
        if share:
            fill_day(today - timedelta(days=back), share, all_slots)
    # Hoy, a medias: desayuno, comida y un snack.
    fill_day(today, 0.62, ("desayuno", "comida", "merienda"))

    kg = 78.6
    for back in range(14, -1, -1):
        kg += random.uniform(-0.42, 0.18)
        rq.put(f"{base}/api/weight", data={"date": (today - timedelta(days=back)).isoformat(), "kg": round(kg, 1)})
    for dish in rq.get(f"{base}/api/dishes").json()["dishes"][:3]:
        rq.patch(f"{base}/api/dishes/{dish['id']}", data={"favorite": True})
    rq.post(f"{base}/api/targets/recalculate")


def capture_theme(browser, base: str, theme: str) -> None:
    out = OUT / theme
    out.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(viewport=MOBILE, device_scale_factor=2, is_mobile=True, has_touch=True, locale="es-ES", timezone_id="Europe/Madrid")
    context.add_init_script(f"localStorage.setItem('kcalia:theme', '{theme}')")
    page = context.new_page()
    page.goto(base)
    page.locator("input[name=username]").fill("demo")
    page.locator("input[name=password]").fill(PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    page.locator("main").wait_for()
    page.wait_for_timeout(2400)
    page.screenshot(path=str(out / "01-hoy.png"))

    page.get_by_role("button", name="Añadir comida").last.click()
    page.locator("#meal-text").wait_for()
    page.wait_for_timeout(700)
    page.screenshot(path=str(out / "02-anadir.png"))
    page.locator("#meal-text").fill("ensalada de atún con tomate y lechuga")
    page.get_by_role("button", name="Analizar comida").click()
    page.get_by_role("heading", name="Revisa y guarda").wait_for()
    page.wait_for_timeout(1400)
    page.screenshot(path=str(out / "03-resultado.png"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    for name, link, file in (("Historial", "Historial", "04-historial"), ("Resumen", "Resumen", "05-resumen"), ("Peso", "Peso", "06-peso"), ("Ajustes", "Ajustes", "07-ajustes")):
        page.get_by_role("link", name=link).click()
        page.get_by_role("heading", name=name, exact=True).wait_for()
        page.wait_for_timeout(2400)
        page.screenshot(path=str(out / f"{file}.png"))
    context.close()


def record_gif(browser, base: str) -> None:
    """Graba el flujo principal (escribir, analizar, ajustar la ración, guardar) y lo convierte a GIF."""
    video_dir = Path(tempfile.mkdtemp(prefix="kcalia-video-"))
    context = browser.new_context(
        viewport=MOBILE, device_scale_factor=1, is_mobile=True, has_touch=True, locale="es-ES", timezone_id="Europe/Madrid",
        record_video_dir=str(video_dir), record_video_size=MOBILE,
    )
    context.add_init_script("localStorage.setItem('kcalia:theme', 'dark')")
    page = context.new_page()
    page.goto(base)
    page.locator("input[name=username]").fill("demo")
    page.locator("input[name=password]").fill(PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    page.locator("main").wait_for()
    page.wait_for_timeout(2600)

    page.get_by_role("button", name="Añadir comida").last.click()
    page.locator("#meal-text").wait_for()
    page.wait_for_timeout(600)
    page.locator("#meal-text").press_sequentially("bocadillo de jamón serrano con tomate y aceite", delay=45)
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Analizar comida").click()
    page.get_by_role("heading", name="Revisa y guarda").wait_for()
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="×1,5").click()
    page.wait_for_timeout(1100)
    page.get_by_role("button", name=" Guardar ·").click()
    page.wait_for_timeout(2600)
    context.close()

    video = next(video_dir.glob("*.webm"))
    gif = ROOT / "docs" / "demo.gif"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-ss", "2.4", "-i", str(video),
            "-vf", "fps=14,scale=300:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
            str(gif),
        ],
        check=True,
    )
    shutil.rmtree(video_dir, ignore_errors=True)
    print(f"· {gif.relative_to(ROOT)} ({gif.stat().st_size / 1024:.0f} KB)")


def build_hero() -> None:
    """Cuatro pantallas en oscuro y cuatro en claro, en una sola imagen para la cabecera del README."""
    from PIL import Image, ImageDraw, ImageFilter

    def strip(theme: str, files: list[str]) -> Image.Image:
        shots = [Image.open(OUT / theme / f"{f}.png").convert("RGB") for f in files]
        width, gap = 300, 26
        thumbs = []
        for shot in shots:
            height = round(shot.height * width / shot.width)
            thumb = shot.resize((width, height), Image.LANCZOS)
            mask = Image.new("L", thumb.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, *thumb.size), radius=34, fill=255)
            thumbs.append((thumb, mask))
        canvas = Image.new("RGB", (len(thumbs) * width + (len(thumbs) + 1) * gap, thumbs[0][0].height + 2 * gap), (0, 0, 0))
        canvas.paste(Image.new("RGB", canvas.size, (11, 12, 14) if theme == "dark" else (238, 236, 229)))
        for index, (thumb, mask) in enumerate(thumbs):
            x = gap + index * (width + gap)
            shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle((x, gap + 12, x + width, gap + 12 + thumb.height), radius=34, fill=(0, 0, 0, 110 if theme == "dark" else 60))
            canvas.paste(shadow.filter(ImageFilter.GaussianBlur(16)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(16)))
            canvas.paste(thumb, (x, gap), mask)
        return canvas

    files = ["01-hoy", "03-resultado", "05-resumen", "06-peso"]
    for theme in ("dark", "light"):
        image = strip(theme, files)
        image.save(ROOT / "docs" / f"hero-{theme}.png", optimize=True)
        print(f"· docs/hero-{theme}.png {image.size}")


def main() -> None:
    if not (DIST / "index.html").exists():
        raise SystemExit("Falta el frontend compilado: cd frontend && npm run build")
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    servers, procs, data = start_servers()
    base = servers["app"]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport=MOBILE, device_scale_factor=2, is_mobile=True, has_touch=True, locale="es-ES", timezone_id="Europe/Madrid")
            context.set_default_timeout(20_000)
            context.add_init_script("localStorage.setItem('kcalia:theme', 'dark')")
            page = context.new_page()
            (OUT / "dark").mkdir(parents=True, exist_ok=True)
            onboard(page, base, OUT / "dark")
            seed(page, base)
            context.close()
            (OUT / "light").mkdir(parents=True, exist_ok=True)
            capture_theme(browser, base, "dark")
            capture_theme(browser, base, "light")
            # El GIF va al final para que "ensalada de atún" siga siendo nueva en las capturas.
            record_gif(browser, base)
            browser.close()
        build_hero()
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=10)
        shutil.rmtree(data, ignore_errors=True)
    print("Listo:", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()

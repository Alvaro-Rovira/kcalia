"""Genera las capturas y el GIF del README a partir de la app real.

    cd frontend && npm run build
    uv run --project backend --group e2e --with pillow python scripts/capture_screenshots.py

Levanta la app con una IA simulada (e2e/fake_ai.py) y datos temporales, hace el onboarding
por la interfaz, siembra un par de semanas de actividad a través de la propia API y captura
en un móvil de 390 px, en oscuro y en claro. Los datos de las capturas son de demostración
y no salen de esta máquina: nada de esto se usa en producción.
"""

import json
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
sys.path.insert(0, str(ROOT / "scripts"))

import httpx
from app_dates import medium
from conftest import DIST, free_port, wait_for
from make_label_photo import make as make_label
from playwright.sync_api import Page, sync_playwright

OUT = ROOT / "docs" / "screenshots"
USER = "alvaro"
PASSWORD = "clave-de-prueba-1"
AI_URL = ""  # se rellena al arrancar: la IA simulada que lee las etiquetas
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
        "OFF_BASE_URL": f"http://127.0.0.1:{ai_port}",
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
    return {"app": f"http://127.0.0.1:{app_port}", "ai": f"http://127.0.0.1:{ai_port}"}, procs, data


def onboard(page: Page, base: str, out: Path) -> None:
    """Registro y onboarding por la interfaz; de paso captura la pantalla del plan."""
    page.goto(base)
    page.get_by_role("heading", name="Inicia sesión").wait_for()
    page.wait_for_timeout(900)
    page.screenshot(path=str(out / "00-acceso.png"))
    page.locator("input[name=username]").fill(USER)
    page.locator("input[name=password]").fill(PASSWORD)
    page.get_by_role("button", name="Créala ahora").click()
    page.get_by_role("heading", name="Crea tu cuenta").wait_for()
    page.wait_for_timeout(700)
    page.screenshot(path=str(out / "00-crear-cuenta.png"))
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
    today = date.today()  # noqa: DTZ011 (la app usa la fecha local del dispositivo)
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
    for kind in ("yogur", "leche", "queso"):
        add_product(page, base, kind)
    seed_tracking(page, base, today)
    seed_training(page, base, today)
    seed_plan(page, base, today)
    # Dos personas piden cuenta: el panel de administración las muestra pendientes.
    for name in ("lucia", "marcos.r"):
        httpx.post(f"{base}/api/auth/register", json={"username": name, "password": PASSWORD}, headers={"Origin": base})


def seed_tracking(page: Page, base: str, today: date) -> None:
    """Agua de la última semana, medidas cada semana y días de entreno con objetivos propios."""
    rq = page.request
    for back in range(6, -1, -1):
        glasses = 5 if back == 0 else random.randint(7, 11)
        for _ in range(glasses):
            day = (today - timedelta(days=back)).isoformat()
            rq.post(f"{base}/api/water", data={"client_id": str(uuid.uuid4()), "date": day, "ml": 250})
    for back, waist, chest, arm, hip in ((14, 86.5, 101.0, 34.0, 98.0), (7, 85.4, 101.5, 34.2, 97.4), (0, 84.6, 101.8, 34.5, 96.9)):
        rq.put(f"{base}/api/measurements", data={"date": (today - timedelta(days=back)).isoformat(), "waist": waist, "chest": chest, "arm": arm, "hip": hip})
    # Entreno lunes, miércoles y viernes con +200 kcal; la sugerencia para cerrar el día, visible a cualquier hora.
    rq.patch(f"{base}/api/prefs", data={"day_types": True, "training_days": [0, 2, 4], "suggest_hour": "00:00"})


# Pesos de partida de cada ejercicio de las rutinas de ejemplo (suben un poco cada semana).
START_KG = {
    "ex-press-banca": 55, "ex-press-inclinado-mancuernas": 18, "ex-press-militar": 35, "ex-elevaciones-laterales": 8,
    "ex-triceps-polea": 20, "ex-dominadas": 0, "ex-remo-barra": 50, "ex-jalon": 45, "ex-curl-barra": 25,
    "ex-face-pull": 15, "ex-sentadilla": 70, "ex-peso-muerto-rumano": 60, "ex-prensa": 120, "ex-curl-femoral": 30,
    "ex-gemelos": 40,
}


def seed_training(page: Page, base: str, today: date) -> None:
    """Dos semanas de rutinas empuje / tirón / pierna con una progresión creíble."""
    rq = page.request
    templates = {t["client_id"]: t for t in rq.get(f"{base}/api/training").json()["templates"]}
    order = [cid for cid in ("tpl-empuje", "tpl-tiron", "tpl-pierna") if cid in templates]
    days = [back for back in range(13, 0, -1) if (today - timedelta(days=back)).weekday() in (0, 2, 4)]
    for index, back in enumerate(days):
        template = templates[order[index % len(order)]]
        week = index // len(order)
        day = today - timedelta(days=back)
        cid = str(uuid.uuid4())
        start = f"{day.isoformat()}T17:{random.randint(10, 40)}:00"
        rq.post(f"{base}/api/workouts", data={"client_id": cid, "date": day.isoformat(), "name": template["name"], "template_cid": template["client_id"], "started_at": start})
        position = 0
        for item in template["exercises"]:
            weight = START_KG.get(item["exercise"], 20) * (1 + 0.04 * week)
            for number in range(item["sets"]):
                reps = max(1, item["reps"] - (1 if number == item["sets"] - 1 else 0))
                body = {"client_id": str(uuid.uuid4()), "exercise": item["exercise"], "reps": reps, "weight": round(weight / 2.5) * 2.5, "position": position}
                rq.post(f"{base}/api/workouts/{cid}/sets", data=body)
                position += 1
        end = f"{day.isoformat()}T18:{random.randint(15, 45)}:00"
        rq.patch(f"{base}/api/workouts/{cid}", data={"ended_at": end, "duration_min": 65, "intensity": "moderada"})


def seed_plan(page: Page, base: str, today: date) -> None:
    """Comidas y cenas planificadas para los próximos días con lo que ya suele comer."""
    rq = page.request
    dishes = rq.get(f"{base}/api/dishes").json()["dishes"]
    picks = [d for d in dishes if d["kcal"] > 350][:4] or dishes[:4]
    for offset in range(4):
        day = (today + timedelta(days=offset)).isoformat()
        for slot, dish in (("comida", picks[offset % len(picks)]), ("cena", picks[(offset + 1) % len(picks)])):
            body = {"client_id": str(uuid.uuid4()), "date": day, "slot": slot, "name": dish["name"], "items": dish["items"], "dish_id": dish["id"]}
            rq.put(f"{base}/api/plan", data=body)


def add_product(page: Page, base: str, kind: str) -> None:
    """Lee la etiqueta (IA simulada) y guarda el producto con su foto, como hace la app."""
    rq = page.request
    httpx.post(f"{AI_URL}/next-label", params={"kind": kind})
    photo = {"name": "etiqueta.jpg", "mimeType": "image/jpeg", "buffer": make_label(kind)}
    draft = rq.post(f"{base}/api/products/scan", multipart={"image": photo}).json()["draft"]
    fields = ("name", "alias", "basis", "kcal100", "protein100", "carbs100", "fat100", "fiber100", "sugars100", "salt100", "unit_label", "unit_grams")
    created = rq.post(f"{base}/api/products", multipart={"data": json.dumps({k: draft[k] for k in fields}), "image": photo})
    assert created.status == 201, created.text()


def scroll_to(locator, top: int = 64) -> None:
    """Deja el elemento arriba de la pantalla (scroll_into_view lo deja pegado al borde o a medias)."""
    locator.evaluate(f"e => window.scrollTo(0, e.getBoundingClientRect().top + window.scrollY - {top})")
    locator.page.wait_for_timeout(900)


def capture_theme(browser, base: str, theme: str) -> None:
    out = OUT / theme
    out.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(viewport=MOBILE, device_scale_factor=2, is_mobile=True, has_touch=True, locale="es-ES", timezone_id="Europe/Madrid")
    context.add_init_script(f"localStorage.setItem('kcalia:theme', '{theme}')")
    page = context.new_page()
    page.goto(base)
    page.locator("input[name=username]").fill(USER)
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

    # Hoy, más abajo: la sugerencia para cerrar el día.
    scroll_to(page.get_by_role("region", name="Sugerencia para cerrar el día"))
    page.screenshot(path=str(out / "12-sugerencia.png"))

    page.get_by_role("link", name="Historial").click()
    page.get_by_role("heading", name="Historial", exact=True).wait_for()
    page.wait_for_timeout(2400)
    page.screenshot(path=str(out / "04-historial.png"))
    page.get_by_role("navigation", name="Historial").get_by_role("link", name="Plan").click()
    page.get_by_role("heading", name="Plan semanal").wait_for()
    page.wait_for_timeout(1200)
    scroll_to(page.get_by_role("region", name=medium(date.today(), capital=True)))  # noqa: DTZ011
    page.screenshot(path=str(out / "13-plan.png"))

    page.get_by_role("link", name="Entreno").click()
    page.get_by_role("heading", name="Rutinas").wait_for()
    page.wait_for_timeout(2200)
    page.screenshot(path=str(out / "14-entreno.png"))
    page.get_by_role("button", name="Empezar Empuje").click()
    card = page.get_by_role("region", name="Press de banca")
    card.get_by_role("button", name="Serie 1").click()
    page.get_by_role("timer").wait_for()
    page.wait_for_timeout(1500)
    page.screenshot(path=str(out / "15-entreno-activo.png"))
    page.get_by_role("button", name="Saltar el descanso").click()
    page.get_by_role("button", name="Terminar").click()
    page.get_by_role("dialog").get_by_role("button", name="Guardar entreno").click()
    page.get_by_text("Entreno guardado").wait_for()

    page.get_by_role("link", name="Progreso").click()
    page.get_by_role("heading", name="Resumen", exact=True).wait_for()
    page.wait_for_timeout(2400)
    page.screenshot(path=str(out / "05-resumen.png"))
    if theme == "dark":
        with page.expect_download() as info:
            page.get_by_role("button", name="Compartir la semana como imagen").click()
        info.value.save_as(ROOT / "docs" / "semana-compartida.png")
        page.wait_for_timeout(600)
    page.get_by_role("navigation", name="Progreso").get_by_role("link", name="Cuerpo").click()
    page.get_by_role("heading", name="Peso", exact=True).wait_for()
    page.wait_for_timeout(2400)
    page.screenshot(path=str(out / "06-peso.png"))
    page.get_by_role("radio", name="Medidas").click()
    page.get_by_role("heading", name="Medidas", exact=True).wait_for()
    page.wait_for_timeout(2000)
    page.screenshot(path=str(out / "16-medidas.png"))

    page.get_by_role("link", name="Ajustes").click()
    page.get_by_role("heading", name="Ajustes", exact=True).wait_for()
    page.wait_for_timeout(1800)
    page.screenshot(path=str(out / "07-ajustes.png"))
    page.get_by_role("button", name="Cuentas, solicitudes y gasto de IA").click()
    page.get_by_role("heading", name="Administración").wait_for()
    page.wait_for_timeout(1800)
    page.screenshot(path=str(out / "17-admin.png"))

    # Productos: la lista con la foto de cada etiqueta, la hoja de revisión y «dos yogures ligeros».
    page.get_by_role("link", name="Historial").click()
    page.get_by_role("radio", name="Productos").click()
    page.get_by_text("Tus productos").wait_for()
    page.wait_for_timeout(1800)
    page.screenshot(path=str(out / "09-productos.png"))
    page.get_by_text("Yogur desnatado ligero sabor limón").first.click()
    page.get_by_role("heading", name="Editar producto").wait_for()
    page.wait_for_timeout(1200)
    page.screenshot(path=str(out / "10-etiqueta.png"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    page.get_by_role("link", name="Hoy").click()
    page.get_by_role("button", name="Añadir comida").last.click()
    page.locator("#meal-text").fill("dos yogures ligeros con una manzana")
    page.get_by_role("button", name="Analizar comida").click()
    page.get_by_role("heading", name="Revisa y guarda").wait_for()
    page.wait_for_timeout(1400)
    page.screenshot(path=str(out / "11-dos-yogures.png"))
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
    page.locator("input[name=username]").fill(USER)
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


def to_gif(video_dir: Path, name: str, start: float, width: int, fps: int, colors: int) -> None:
    video = next(video_dir.glob("*.webm"))
    gif = ROOT / "docs" / name
    palette = f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors={colors}:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-i", str(video), "-vf", palette, str(gif)], check=True)
    shutil.rmtree(video_dir, ignore_errors=True)
    print(f"· {gif.relative_to(ROOT)} ({gif.stat().st_size / 1024:.0f} KB)")


def record_workout_gif(browser, base: str) -> None:
    """Graba un entreno: empezar la rutina, apuntar series con el descanso en marcha y terminar."""
    video_dir = Path(tempfile.mkdtemp(prefix="kcalia-video-"))
    context = browser.new_context(
        viewport=MOBILE, device_scale_factor=1, is_mobile=True, has_touch=True, locale="es-ES", timezone_id="Europe/Madrid",
        record_video_dir=str(video_dir), record_video_size=MOBILE,
    )
    context.set_default_timeout(20_000)
    context.add_init_script("localStorage.setItem('kcalia:theme', 'dark')")
    page = context.new_page()
    page.goto(base)
    page.locator("input[name=username]").fill(USER)
    page.locator("input[name=password]").fill(PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    page.locator("main").wait_for()
    page.wait_for_timeout(1500)

    page.get_by_role("link", name="Entreno").click()
    page.get_by_role("heading", name="Rutinas").wait_for()
    page.wait_for_timeout(1600)
    page.get_by_role("button", name="Empezar Pierna").click()
    card = page.get_by_role("region", name="Sentadilla")
    card.wait_for()
    page.wait_for_timeout(1200)
    card.get_by_role("button", name="Peso: más").click()
    page.wait_for_timeout(500)
    card.get_by_role("button", name="Serie 1").click()
    page.get_by_role("timer").wait_for()
    page.wait_for_timeout(2600)
    page.get_by_role("button", name="Saltar el descanso").click()
    page.wait_for_timeout(700)
    card.get_by_role("button", name="Repetir").click()
    page.wait_for_timeout(1800)
    page.get_by_role("button", name="Saltar el descanso").click()
    page.wait_for_timeout(600)
    page.get_by_role("button", name="Terminar").click()
    dialog = page.get_by_role("dialog")
    page.wait_for_timeout(1200)
    dialog.get_by_role("radio", name="Intensa").click()
    page.wait_for_timeout(900)
    dialog.get_by_role("button", name="Guardar entreno").click()
    page.get_by_text("Entreno guardado").wait_for()
    page.wait_for_timeout(2400)
    context.close()
    to_gif(video_dir, "demo-entreno.gif", 1.5, 280, 10, 80)


def record_label_gif(browser, base: str) -> None:
    """Graba el flujo de productos: foto de la etiqueta -> lectura -> revisión -> «tres galletas integrales»."""
    video_dir = Path(tempfile.mkdtemp(prefix="kcalia-video-"))
    photo = Path(tempfile.mkdtemp(prefix="kcalia-label-")) / "etiqueta.jpg"
    photo.write_bytes(make_label("galletas"))
    httpx.post(f"{AI_URL}/next-label", params={"kind": "galletas"})
    context = browser.new_context(
        viewport=MOBILE, device_scale_factor=1, is_mobile=True, has_touch=True, locale="es-ES", timezone_id="Europe/Madrid",
        record_video_dir=str(video_dir), record_video_size=MOBILE,
    )
    context.set_default_timeout(20_000)
    context.add_init_script("localStorage.setItem('kcalia:theme', 'dark')")
    page = context.new_page()
    page.goto(base)
    page.locator("input[name=username]").fill(USER)
    page.locator("input[name=password]").fill(PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    page.locator("main").wait_for()
    page.wait_for_timeout(1800)

    page.get_by_role("link", name="Historial").click()
    page.get_by_role("radio", name="Productos").click()
    page.get_by_text("Tus productos").wait_for()
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="Añadir", exact=True).click()
    page.get_by_text("Hacer foto a la etiqueta").wait_for()
    page.wait_for_timeout(1700)
    page.locator("input[type=file]:not([capture])").set_input_files(str(photo))
    page.get_by_role("heading", name="Revisa la etiqueta").wait_for()
    page.wait_for_timeout(2800)
    page.get_by_role("button", name="Guardar producto").click()
    page.get_by_text("Guardado: galletas integrales").wait_for()
    page.wait_for_timeout(1500)

    page.get_by_role("link", name="Hoy").click()
    page.wait_for_timeout(900)
    page.get_by_role("button", name="Añadir comida").last.click()
    page.locator("#meal-text").wait_for()
    page.wait_for_timeout(500)
    page.locator("#meal-text").press_sequentially("tres galletas integrales", delay=70)
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Analizar comida").click()
    page.get_by_text("Sin IA · con tu etiqueta").wait_for()
    page.wait_for_timeout(2600)
    page.get_by_role("button", name=" Guardar ·").click()
    page.wait_for_timeout(2200)
    context.close()

    video = next(video_dir.glob("*.webm"))
    gif = ROOT / "docs" / "demo-etiqueta.gif"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-ss", "1.8", "-i", str(video),
            "-vf", "fps=10,scale=280:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=80:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5",
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

    files = ["01-hoy", "03-resultado", "04-historial", "14-entreno"]
    for theme in ("dark", "light"):
        image = strip(theme, files)
        image.save(ROOT / "docs" / f"hero-{theme}.png", optimize=True)
        print(f"· docs/hero-{theme}.png {image.size}")


def main() -> None:
    if not (DIST / "index.html").exists():
        raise SystemExit("Falta el frontend compilado: cd frontend && npm run build")
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    global AI_URL
    servers, procs, data = start_servers()
    base, AI_URL = servers["app"], servers["ai"]
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
            record_label_gif(browser, base)
            record_workout_gif(browser, base)
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

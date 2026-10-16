"""Datos extremos en un móvil de 375 px: ninguna página se rompe, se desborda ni da errores; los datos no se duplican ni
se pierden al exportar e importar. Va después de test_flow (su registro espera que no haya ninguna cuenta)."""

import pytest
from app_dates import app_today
from conftest import PASSWORD
from playwright.sync_api import Page, expect

PAGES = ["/", "/historial", "/resumen", "/peso", "/entreno", "/plan", "/ajustes", "/admin", "/no-existe"]
LONG_WORD = "Superextraordinariamentelarguísimoplatoconnombreinterminable" * 3


@pytest.fixture(scope="module")
def page(browser_instance, servers):
    context = browser_instance.new_context(viewport={"width": 375, "height": 812}, locale="es-ES")
    page = context.new_page()
    page.errors = []  # type: ignore[attr-defined]
    page.console_errors = []  # type: ignore[attr-defined]
    page.on("pageerror", lambda error: page.errors.append(str(error)))  # type: ignore[attr-defined]
    page.on(
        "console",
        lambda msg: page.console_errors.append(msg.text) if msg.type == "error" else None,  # type: ignore[attr-defined]
    )
    origin = {"Origin": servers["app"]}
    api = page.request
    page.goto(servers["app"])
    credentials = {"username": "alvaro", "password": PASSWORD}
    if not api.post(servers["app"] + "/api/auth/login", data=credentials, headers=origin).ok:
        assert api.post(servers["app"] + "/api/auth/register", data=credentials, headers=origin).ok
    profile = dict(sex="hombre", age=19, height_cm=167, weight_kg=65, activity="medio", goal="recomposicion")
    assert api.put(servers["app"] + "/api/profile", data=profile, headers=origin).ok
    day = app_today().isoformat()
    item = {"name": LONG_WORD.lower()[:120], "qty": 1, "unit": "g", "grams": 5000, "kcal": 6000, "protein": 600,
            "carbs": 1200, "fat": 600, "manual": True}  # fmt: skip
    for n, slot in enumerate(["desayuno", "comida", "cena"]):
        body = {"client_id": f"explora-{n:04d}", "date": day, "slot": slot, "name": LONG_WORD[:160], "text": LONG_WORD,
                "items": [item] * 30, "source": "manual", "dish_id": None}  # fmt: skip
        response = api.post(servers["app"] + "/api/meals", data=body, headers=origin)
        assert response.ok, response.text()
    api.put(servers["app"] + "/api/weight", data={"date": day, "kg": 65}, headers=origin)
    yield page
    context.close()


def test_explorar_paginas(page: Page, servers):
    problems = []
    for path in PAGES:
        page.errors.clear()  # type: ignore[attr-defined]
        page.console_errors.clear()  # type: ignore[attr-defined]
        page.goto(servers["app"] + path)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(400)
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        if overflow > 1:
            wide = page.evaluate(
                """() => [...document.querySelectorAll('body *')]
                  .filter(e => e.getBoundingClientRect().right > window.innerWidth + 1)
                  .slice(0, 3).map(e => e.tagName + '.' + (e.className || '').toString().slice(0, 60) + ' «'
                    + (e.textContent || '').trim().slice(0, 40) + '»')"""
            )
            problems.append(f"{path}: se sale {overflow} px por la derecha: {wide}")
        if page.errors:  # type: ignore[attr-defined]
            problems.append(f"{path}: errores de JS: {page.errors[:3]}")  # type: ignore[attr-defined]
        if page.console_errors:  # type: ignore[attr-defined]
            problems.append(f"{path}: consola: {page.console_errors[:3]}")  # type: ignore[attr-defined]
    assert not problems, "\n".join(problems)


def test_datos_doble_envio_y_exportar_importar(page: Page, servers):
    origin = {"Origin": servers["app"]}
    api, base = page.request, servers["app"]
    day = app_today().isoformat()
    item = {"name": "pan", "qty": 1, "unit": "g", "grams": 40, "kcal": 100, "protein": 3, "carbs": 20, "fat": 1,
            "manual": True}  # fmt: skip
    body = {"client_id": "doble-0001", "date": day, "slot": "snack", "name": "pan", "text": "pan", "items": [item],
            "source": "manual", "dish_id": None}  # fmt: skip
    first = api.post(base + "/api/meals", data=body, headers=origin)
    again = api.post(base + "/api/meals", data=body, headers=origin)
    meals = api.get(base + f"/api/meals?date={day}").json()["meals"]
    assert first.ok and again.ok  # el reintento no da error...
    assert sum(m["client_id"] == "doble-0001" for m in meals) == 1  # ...ni duplica la comida

    exported = api.get(base + "/api/export/json").json()
    counts = {k: len(v) for k, v in exported.items() if isinstance(v, list)}
    assert api.post(base + "/api/data/delete", data={"password": PASSWORD}, headers=origin).ok
    imported = api.post(base + "/api/import/json", multipart={"file": {"name": "k.json", "mimeType": "application/json",
                        "buffer": __import__("json").dumps(exported).encode()}}, headers=origin)  # fmt: skip
    assert imported.ok, imported.text()
    again_exported = api.get(base + "/api/export/json").json()
    again_counts = {k: len(v) for k, v in again_exported.items() if isinstance(v, list)}
    assert again_counts == counts


CORRUPT_CACHE = """async () => {
  const db = await new Promise((ok, ko) => { const r = indexedDB.open('keyval-store'); r.onsuccess = () => ok(r.result); r.onerror = ko })
  const store = () => db.transaction('keyval', 'readwrite').objectStore('keyval')
  const value = await new Promise((ok) => { const r = store().get('kcalia:cache'); r.onsuccess = () => ok(r.result) })
  if (!value) return false
  const data = typeof value === 'string' ? JSON.parse(value) : value
  const boot = data.clientState.queries.find((q) => q.queryKey[0] === 'bootstrap')
  boot.state.data.user = null  // una copia guardada que ya no encaja con la app
  await new Promise((ok) => { const r = store().put(typeof value === 'string' ? JSON.stringify(data) : data, 'kcalia:cache'); r.onsuccess = ok })
  return true
}"""


def test_una_copia_local_rota_no_deja_la_app_en_blanco(page: Page, servers):
    page.goto(servers["app"] + "/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)  # la caché se guarda con un pequeño retraso
    assert page.evaluate(CORRUPT_CACHE)
    page.context.set_offline(True)  # sin red, la app solo tiene la copia rota
    page.reload()
    # Antes, la pantalla en blanco; ahora, un aviso con salida.
    expect(page.get_by_role("alert")).to_contain_text("Algo ha fallado al mostrar esta pantalla")
    page.context.set_offline(False)
    page.get_by_role("button", name="Borrar la copia de este dispositivo y recargar").click()
    expect(page.get_by_role("link", name="Ajustes")).to_be_visible()

"""Flujo principal de extremo a extremo, en un móvil de 390 px:
onboarding -> registrar comidas (IA, historial, aproximada, caché) -> resumen -> sin conexión -> ajustes.

Es un único recorrido en orden porque cada paso parte del estado que dejó el anterior.
"""

import httpx
import pytest
from playwright.sync_api import Page, expect

from conftest import PASSWORD

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(scope="module")
def page(browser_instance, servers):
    context = browser_instance.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        locale="es-ES",
        timezone_id="Europe/Madrid",
    )
    context.set_default_timeout(15_000)
    tab = context.new_page()
    errors: list[str] = []
    tab.on("pageerror", lambda e: errors.append(str(e)))
    # Errores de consola (p. ej. una CSP que bloquea algo), salvo los propios de estar sin red.
    tab.on(
        "console",
        lambda m: errors.append(m.text)
        if m.type == "error" and "ERR_INTERNET_DISCONNECTED" not in m.text and "Failed to load resource" not in m.text
        else None,
    )
    tab.errors = errors  # type: ignore[attr-defined]
    tab.goto(servers["app"])
    yield tab
    context.close()


def add_meal(page: Page, text: str) -> None:
    page.get_by_role("button", name="Añadir comida").last.click()
    page.locator("#meal-text").fill(text)
    page.get_by_role("button", name="Analizar comida").click()


def test_00_cabeceras_y_head(servers):
    for method in ("GET", "HEAD"):
        page = httpx.request(method, servers["app"] + "/")
        assert page.status_code == 200, method
        assert "default-src 'self'" in page.headers["content-security-policy"]
        assert page.headers["cache-control"] == "no-cache"
    # Las metas Open Graph salen con URL absoluta y sin marcadores sin sustituir.
    assert "__ORIGIN__" not in httpx.get(servers["app"] + "/").text
    assert httpx.head(servers["app"] + "/api/health").status_code == 200
    assert httpx.head(servers["app"] + "/sw.js").headers["cache-control"] == "no-cache"
    manifest = httpx.get(servers["app"] + "/manifest.webmanifest").json()
    assert manifest["display"] == "standalone" and manifest["lang"] == "es-ES"
    assert any(icon["purpose"] == "maskable" for icon in manifest["icons"])


def test_01_registro_y_onboarding(page: Page):
    expect(page.get_by_role("heading", name="Crea tu cuenta")).to_be_visible()
    page.locator("input[name=username]").fill("alvaro")
    page.locator("input[name=password]").fill(PASSWORD)
    page.get_by_role("button", name="Crear cuenta").click()

    page.get_by_role("button", name="Empezar", exact=True).click()
    page.get_by_role("radio", name="Hombre").click()
    expect(page.get_by_role("heading", name="¿Cuántos años tienes?")).to_be_visible()
    page.get_by_role("button", name="Continuar").click()
    page.get_by_role("button", name="Aumentar peso").click()  # 75,5 kg
    page.get_by_role("button", name="Continuar").click()
    page.get_by_role("button", name="Continuar").click()  # altura por defecto
    page.get_by_role("radio", name=" Moderado").click()
    page.get_by_role("radio", name="Definición ligera").click()
    page.get_by_role("button", name="Saltar").click()  # sin peso objetivo

    expect(page.get_by_text("Cómo lo he calculado")).to_be_visible()
    # Mifflin-St Jeor (75,5 kg, 172 cm, 30 años, hombre) × 1,55 × 0,85
    expect(page.get_by_text("kcal al día")).to_be_visible()
    page.get_by_role("button", name="Empezar con este plan").click()
    expect(page.get_by_text("Aún no has apuntado nada")).to_be_visible()


def test_02_registrar_con_ia(page: Page, ai_calls):
    before = ai_calls()
    add_meal(page, "pechuga de pollo con arroz")
    expect(page.get_by_role("heading", name="Revisa y guarda")).to_be_visible()
    expect(page.get_by_text("Analizado con IA")).to_be_visible()
    page.get_by_role("button", name="×1,5").click()
    page.get_by_role("button", name=" Guardar ·").click()
    expect(page.get_by_role("button", name="Deshacer").first).to_be_visible()
    expect(page.get_by_role("button", name="Pechuga de pollo con arroz").first).to_be_visible()
    assert ai_calls() == before + 1


def test_03_historial_exacto_no_gasta_ia(page: Page, ai_calls):
    before = ai_calls()
    add_meal(page, "Una PECHUGA de pollo, con arroz!")
    # Coincidencia exacta tras normalizar: se añade sola, sin pasar por la IA.
    expect(page.get_by_text("sin gastar IA").first).to_be_visible()
    assert ai_calls() == before
    expect(page.get_by_role("button", name="Pechuga de pollo con arroz")).to_have_count(2)


def test_04_coincidencia_aproximada_pregunta(page: Page, ai_calls):
    add_meal(page, "yogur griego con nueces")  # primera vez: IA
    expect(page.get_by_role("heading", name="Revisa y guarda")).to_be_visible()
    page.get_by_role("button", name=" Guardar ·").click()
    expect(page.get_by_role("button", name="Deshacer").first).to_be_visible()

    before = ai_calls()
    add_meal(page, "yogur griego con nuezes")  # errata: parecido, no idéntico
    expect(page.get_by_role("heading", name="¿Es esta comida?")).to_be_visible()
    page.get_by_role("button", name="Sí, es esta").click()
    expect(page.get_by_text("sin gastar IA").first).to_be_visible()
    assert ai_calls() == before


def test_05_peso_y_resumen(page: Page):
    page.get_by_role("link", name="Peso").click()
    page.get_by_role("button", name="Apuntar").first.click()
    page.get_by_role("button", name="Guardar", exact=True).click()
    expect(page.get_by_text("Media 7 días")).to_be_visible()

    page.get_by_role("link", name="Resumen").click()
    expect(page.get_by_role("heading", name="Resumen")).to_be_visible()
    expect(page.get_by_text("Adherencia").first).to_be_visible()
    expect(page.get_by_text("Media diaria")).to_be_visible()
    expect(page.get_by_text("Balance total")).to_be_visible()
    expect(page.get_by_text("A este ritmo", exact=False)).to_be_visible()
    expect(page.get_by_role("heading", name="Logros")).to_be_visible()


def test_06_ajustes_muestran_el_ahorro(page: Page, servers):
    page.get_by_role("link", name="Ajustes").click()
    expect(page.get_by_text("consultas a la IA ahorradas")).to_be_visible()
    stats = page.request.get(f"{servers['app']}/api/stats").json()
    assert stats["ai"]["saved_total"] >= 2
    assert page.request.get(f"{servers['app']}/api/export/meals.csv").ok
    page.get_by_role("link", name="Hoy").click()


def test_07_sin_conexion(page: Page, servers):
    context = page.context
    # Con el service worker instalado y controlando la página.
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.reload()
    expect(page.get_by_role("button", name="Pechuga de pollo con arroz").first).to_be_visible()
    page.wait_for_timeout(1500)  # la caché se vuelca a IndexedDB

    context.set_offline(True)
    page.reload()
    # El diario se ve entero sin red.
    expect(page.get_by_role("button", name="Pechuga de pollo con arroz").first).to_be_visible()
    expect(page.get_by_text("Sin conexión")).to_be_visible()

    # Una comida del historial se añade y queda pendiente de sincronizar.
    page.get_by_role("button", name="Añadir comida").last.click()
    page.get_by_role("button", name="Añadir Yogur griego con nueces", exact=False).first.click()
    expect(page.get_by_text("1 cambio pendiente")).to_be_visible()

    # Una comida nueva necesita IA: aviso amable, no un error.
    page.get_by_role("button", name="Añadir comida").last.click()
    page.locator("#meal-text").fill("una ensalada césar con pollo")
    page.get_by_role("button", name="Analizar comida").click()
    expect(page.get_by_text("Esta comida es nueva")).to_be_visible()
    page.keyboard.press("Escape")

    # Al volver la red se sincroniza sola.
    context.set_offline(False)
    expect(page.get_by_text("cambio pendiente")).to_have_count(0, timeout=20_000)
    total = page.evaluate(
        "fetch('/api/days?start=2000-01-01&end=2100-01-01').then(r => r.json()).then(d => d.days.reduce((n, x) => n + x.meals, 0))"
    )
    assert total == 5  # pollo ×2, yogur ×2 y el yogur añadido sin conexión


def test_08_cerrar_sesion_y_volver_a_entrar(page: Page):
    page.get_by_role("link", name="Ajustes").click()
    page.get_by_role("button", name="Cerrar sesión").click()
    expect(page.get_by_role("heading", name="Hola de nuevo")).to_be_visible()
    page.locator("input[name=username]").fill("alvaro")
    page.locator("input[name=password]").fill("incorrecta-123")
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_text("Usuario o contraseña incorrectos")).to_be_visible()
    page.locator("input[name=password]").fill(PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_role("button", name="Pechuga de pollo con arroz").first).to_be_visible()
    assert not page.errors  # type: ignore[attr-defined]

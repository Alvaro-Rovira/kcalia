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
    # El HTML lleva el CSS y el tema en línea (con hash en la CSP) para pintar sin más viajes a la red.
    root = httpx.get(servers["app"] + "/")
    assert "<style>" in root.text and 'href="/assets/index-' not in root.text.split("</head>")[0].replace('rel="modulepreload"', "")
    assert "'sha256-" in root.headers["content-security-policy"]
    # Las metas Open Graph salen con URL absoluta y sin marcadores sin sustituir.
    assert "__ORIGIN__" not in httpx.get(servers["app"] + "/").text
    assert httpx.head(servers["app"] + "/api/health").status_code == 200
    assert httpx.head(servers["app"] + "/sw.js").headers["cache-control"] == "no-cache"
    manifest = httpx.get(servers["app"] + "/manifest.webmanifest").json()
    assert manifest["display"] == "standalone" and manifest["lang"] == "es-ES"
    assert any(icon["purpose"] == "maskable" for icon in manifest["icons"])


def test_01_registro_y_onboarding(page: Page):
    # La puerta de entrada es el inicio de sesión; crear cuenta es una opción mientras no exista ninguna.
    expect(page.get_by_role("heading", name="Inicia sesión")).to_be_visible()
    page.locator("input[name=username]").fill("alvaro")
    page.locator("input[name=password]").fill(PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_text("Todavía no existe ninguna cuenta")).to_be_visible()

    page.get_by_role("button", name="Créala ahora").click()
    expect(page.get_by_role("heading", name="Crea tu cuenta")).to_be_visible()
    # Se puede volver atrás sin perder lo escrito.
    page.get_by_role("button", name="Inicia sesión").click()
    expect(page.get_by_role("heading", name="Inicia sesión")).to_be_visible()
    expect(page.locator("input[name=username]")).to_have_value("alvaro")
    page.get_by_role("button", name="Créala ahora").click()
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
    # Con la cuenta ya creada el registro está cerrado: no se ofrece crear otra.
    expect(page.get_by_role("button", name="Créala ahora")).to_have_count(0)
    page.locator("input[name=username]").fill("alvaro")
    page.locator("input[name=password]").fill("incorrecta-123")
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_text("Usuario o contraseña incorrectos")).to_be_visible()
    page.locator("input[name=password]").fill(PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_role("button", name="Pechuga de pollo con arroz").first).to_be_visible()
    assert not page.errors  # type: ignore[attr-defined]


def test_09_producto_desde_la_foto_de_su_etiqueta(page: Page, ai_calls, tmp_path):
    """Foto de una etiqueta -> producto guardado -> «dos yogures ligeros» multiplica sus cifras, sin IA."""
    data_url = page.evaluate(
        """() => { const c = document.createElement('canvas'); c.width = 600; c.height = 420
          const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 600, 420); x.fillStyle = '#111'
          x.font = '28px sans-serif'; x.fillText('Información nutricional por 100 g', 24, 60)
          x.fillText('Energía 187 kJ / 44 kcal', 24, 120); return c.toDataURL('image/jpeg', 0.9) }"""
    )
    import base64

    photo = tmp_path / "etiqueta.jpg"
    photo.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))

    page.get_by_role("link", name="Historial").click()
    page.get_by_role("radio", name="Productos").click()
    expect(page.get_by_text("Aún no tienes productos")).to_be_visible()
    page.get_by_role("button", name="Guardar una etiqueta").click()
    page.locator("input[type=file]:not([capture])").set_input_files(str(photo))

    # La IA (simulada) lee la tabla; se revisa antes de guardar.
    expect(page.get_by_role("heading", name="Revisa la etiqueta")).to_be_visible()
    expect(page.get_by_role("textbox", name="Calorías")).to_have_value("44")
    expect(page.get_by_label("Cómo lo escribirás al apuntar")).to_have_value("yogur ligero")
    expect(page.get_by_text("«2 yogur ligero» =")).to_be_visible()
    expect(page.get_by_text("110 kcal").first).to_be_visible()
    page.get_by_role("button", name="Guardar producto").click()
    expect(page.get_by_text("Guardado: yogur ligero")).to_be_visible()
    expect(page.get_by_role("button", name="Yogur desnatado ligero sabor limón").first).to_be_visible()

    # Escribir «dos yogures ligeros» usa la etiqueta: ni una consulta a la IA.
    before = ai_calls()
    page.get_by_role("link", name="Hoy").click()
    add_meal(page, "dos yogures ligeros")
    expect(page.get_by_text("Sin IA · con tu etiqueta")).to_be_visible()
    expect(page.get_by_role("button", name="Guardar · 110 kcal")).to_be_visible()
    page.get_by_role("button", name="×1,5", exact=True).click()
    expect(page.get_by_role("button", name="Guardar · 165 kcal")).to_be_visible()
    page.get_by_role("button", name="Guardar · 165 kcal").click()
    expect(page.get_by_role("button", name="Deshacer").first).to_be_visible()
    assert ai_calls() == before

    # También sin conexión: el producto ya está en el móvil.
    page.wait_for_timeout(1500)
    page.context.set_offline(True)
    add_meal(page, "un yogur ligero")
    expect(page.get_by_text("Sin IA · con tu etiqueta")).to_be_visible()
    page.get_by_role("button", name="Guardar · 55 kcal").click()
    expect(page.get_by_text("cambio pendiente").first).to_be_visible()
    page.context.set_offline(False)
    expect(page.get_by_text("cambio pendiente")).to_have_count(0, timeout=20_000)

    # Cuenta como consulta ahorrada y el producto sabe cuántas veces se ha usado.
    stats = page.request.get(page.url.split("/")[0] + "//" + page.url.split("/")[2] + "/api/stats").json()
    assert stats["ai"]["saved"]["saved_product"] == 2
    assert not page.errors  # type: ignore[attr-defined]


def test_10_solicitud_de_cuenta_aprobada_desde_el_panel(page: Page, browser_instance, servers):
    """Otra persona solicita cuenta -> ve que está pendiente -> el admin la aprueba en /admin -> ya puede entrar."""
    other = browser_instance.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, locale="es-ES")
    tab = other.new_page()
    tab.goto(servers["app"])
    tab.get_by_role("button", name="Solicítala").click()
    expect(tab.get_by_role("heading", name="Solicita una cuenta")).to_be_visible()
    tab.locator("input[name=username]").fill("lucia")
    tab.locator("input[name=password]").fill("otra-clave-segura-7")
    tab.get_by_role("button", name="Enviar solicitud").click()
    expect(tab.get_by_role("heading", name="Solicitud enviada")).to_be_visible()
    tab.get_by_role("button", name="Ir a iniciar sesión").click()
    tab.locator("input[name=username]").fill("lucia")
    tab.locator("input[name=password]").fill("otra-clave-segura-7")
    tab.get_by_role("button", name="Entrar").click()
    expect(tab.get_by_role("heading", name="Tu cuenta está pendiente de aprobación")).to_be_visible()
    # Sin aprobar no puede usar nada, tampoco la IA.
    assert tab.request.post(servers["app"] + "/api/meals/resolve", data={"text": "una pera"}).status == 403

    # El admin ve la solicitud con su indicador y la aprueba.
    page.goto(servers["app"] + "/ajustes")
    expect(page.get_by_text("1 pendiente")).to_be_visible()
    page.get_by_role("button", name="Cuentas, solicitudes y gasto de IA").click()
    expect(page.get_by_role("heading", name="Administración")).to_be_visible()
    expect(page.get_by_text("Solicitada")).to_be_visible()
    page.get_by_role("button", name="Aprobar").click()
    expect(page.get_by_text("lucia ya puede entrar")).to_be_visible()
    expect(page.get_by_text("aprobó a")).to_be_visible()

    tab.get_by_role("button", name="Comprobar de nuevo").click()
    expect(tab.get_by_role("button", name="Empezar", exact=True)).to_be_visible()  # su propio cuestionario inicial
    # Una cuenta normal no tiene panel de administración.
    assert tab.request.get(servers["app"] + "/api/admin/overview").status == 403
    other.close()
    assert not page.errors  # type: ignore[attr-defined]


def api_get(page: Page, servers, path: str):
    return page.request.get(servers["app"] + path).json()


def wait_until(check, timeout: float = 15) -> None:
    """Espera a que la cola offline haya llevado los cambios al servidor."""
    import time

    deadline = time.time() + timeout
    while not check():
        assert time.time() < deadline, "no se ha sincronizado a tiempo"
        time.sleep(0.25)


def test_11_ingrediente_a_mano(page: Page, servers):
    page.goto(servers["app"])
    page.get_by_role("button", name="Pechuga de pollo con arroz").first.click()
    sheet = page.get_by_role("dialog")
    expect(sheet.get_by_role("heading", name="Detalle de la comida")).to_be_visible()
    sheet.get_by_role("button", name="Añadir ingrediente a mano").click()
    sheet.get_by_placeholder("Por ejemplo: queso fresco batido").fill("salsa de yogur casera")
    sheet.get_by_label("Gramos del ingrediente").fill("50")
    sheet.get_by_label("Calorías", exact=True).fill("120")
    sheet.get_by_label("Proteínas en gramos").fill("3")
    sheet.get_by_label("Hidratos en gramos").fill("4")
    sheet.get_by_label("Grasas en gramos").fill("10")
    sheet.get_by_role("button", name="Añadir · 60 kcal").click()
    expect(sheet.get_by_text("Salsa de yogur casera")).to_be_visible()
    sheet.get_by_role("button", name="Guardar cambios").click()
    expect(page.get_by_text("Cambios guardados")).to_be_visible()
    expect(page.get_by_text("cambio pendiente")).to_have_count(0, timeout=15_000)
    wait_until(
        lambda: any(
            f["name"] == "salsa de yogur casera" and f["kcal100"] == 120 for f in api_get(page, servers, "/api/foods")["foods"]
        )
    )

    # La próxima vez sale al autocompletar (también sin red: viaja en los datos del móvil).
    page.get_by_role("button", name="Pechuga de pollo con arroz").first.click()
    page.get_by_role("dialog").get_by_role("button", name="Añadir ingrediente a mano").click()
    page.get_by_role("dialog").get_by_placeholder("Por ejemplo: queso fresco batido").fill("salsa yog")
    page.get_by_role("option").filter(has_text="Salsa de yogur casera").click()
    expect(page.get_by_role("dialog").get_by_label("Calorías", exact=True)).to_have_value("120")
    page.keyboard.press("Escape")


def test_12_copiar_comida_y_dia(page: Page, servers):
    from datetime import date, timedelta

    page.goto(servers["app"])
    today = date.today().isoformat()
    on_server = len(api_get(page, servers, f"/api/meals?date={today}")["meals"])
    rows = page.get_by_role("button", name="Pechuga de pollo con arroz")
    before = rows.count()
    rows.first.click()
    page.get_by_role("dialog").get_by_role("button", name="Copiar a hoy").click()
    expect(page.get_by_text("Copiada a hoy")).to_be_visible()
    expect(rows).to_have_count(before + 1)

    today_meals = on_server + 1
    wait_until(lambda: len(api_get(page, servers, f"/api/meals?date={today}")["meals"]) == today_meals)
    page.get_by_role("button", name="Copiar este día a otro").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("radio", name="Ayer").click()
    dialog.get_by_role("button", name="Copiar a ayer").click()
    expect(page.get_by_text(f"{today_meals} comidas copiadas a ayer")).to_be_visible()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    wait_until(lambda: len(api_get(page, servers, f"/api/meals?date={yesterday}")["meals"]) == today_meals)


def test_13_codigo_de_barras(page: Page, servers, ai_calls):
    before = ai_calls()
    page.goto(servers["app"] + "/historial")
    page.get_by_role("radio", name="Productos").click()
    page.get_by_role("button", name="Añadir", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("button", name="Escanear el código de barras").click()
    # En las pruebas no hay cámara: se escribe el código a mano.
    dialog.get_by_label("Código de barras").fill("8410000123456")
    dialog.get_by_role("button", name="Buscar").click()
    expect(dialog.get_by_role("heading", name="Revisa el producto")).to_be_visible()
    expect(dialog.get_by_label("Nombre del producto")).to_have_value("Queso fresco batido 0 % (Marca Blanca)")
    expect(dialog.get_by_role("textbox", name="Calorías")).to_have_value("46")
    expect(dialog.get_by_text("Código de barras 8410000123456")).to_be_visible()
    dialog.get_by_role("button", name="Guardar producto").click()
    expect(page.get_by_text("Guardado: queso fresco batido 0 %")).to_be_visible()
    assert ai_calls() == before  # Open Food Facts no es IA

    # Volver a escanearlo lo reconoce sin buscar fuera.
    page.get_by_role("button", name="Añadir", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Escanear el código de barras").click()
    page.get_by_role("dialog").get_by_label("Código de barras").fill("8410000123456")
    page.get_by_role("dialog").get_by_role("button", name="Buscar").click()
    expect(page.get_by_text("Ya lo tienes guardado")).to_be_visible()
    expect(page.get_by_role("heading", name="Editar producto")).to_be_visible()
    page.keyboard.press("Escape")

    # Un código que Open Food Facts no tiene: se ofrece la foto de la etiqueta.
    page.get_by_role("button", name="Añadir", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Escanear el código de barras").click()
    page.get_by_role("dialog").get_by_label("Código de barras").fill("8410000999990")
    page.get_by_role("dialog").get_by_role("button", name="Buscar").click()
    expect(page.get_by_text("Este código no está en Open Food Facts")).to_be_visible()
    expect(page.get_by_role("dialog").get_by_role("button", name="Hacer foto a la etiqueta")).to_be_visible()
    page.keyboard.press("Escape")
    assert not page.errors  # type: ignore[attr-defined]


def test_14_agua_con_y_sin_conexion(page: Page, servers):
    from datetime import date

    today = date.today().isoformat()
    page.goto(servers["app"])
    water = page.get_by_role("region", name="Agua")
    expect(water.get_by_text("de 2,75 L")).to_be_visible()  # 75,5 kg × 35 ml, redondeado a 250
    water.get_by_role("button", name="Añadir 250 ml de agua").click()
    water.get_by_role("button", name="Añadir 500 ml de agua").click()
    expect(water.get_by_text("750 ml", exact=True)).to_be_visible()
    wait_until(lambda: api_get(page, servers, f"/api/water?date={today}")["total_ml"] == 750)

    # Sin red se suma igual y se sincroniza al volver.
    page.wait_for_timeout(1000)
    page.context.set_offline(True)
    water.get_by_role("button", name="Otra").click()
    water.get_by_label("Mililitros de agua").fill("330")
    water.get_by_role("button", name="Añadir esa cantidad").click()
    expect(water.get_by_text("1,08 L", exact=True)).to_be_visible()
    expect(page.get_by_text("cambio pendiente").first).to_be_visible()
    page.context.set_offline(False)
    wait_until(lambda: api_get(page, servers, f"/api/water?date={today}")["total_ml"] == 1080)

    # Deshacer quita solo el último (su aviso es el más reciente).
    water.get_by_role("button", name="Añadir 250 ml de agua").click()
    page.get_by_role("status").filter(has_text="+250 ml de agua").get_by_role("button", name="Deshacer").last.click()
    expect(water.get_by_text("1,08 L", exact=True)).to_be_visible()

    page.get_by_role("link", name="Resumen").click()
    expect(page.get_by_role("region", name="Agua de la semana")).to_be_visible()
    page.get_by_role("link", name="Hoy").click()

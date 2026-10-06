"""Genera la foto de una etiqueta nutricional española (para capturas y pruebas, no es una foto real).

    uv run --with pillow python scripts/make_label_photo.py yogur salida.jpg
"""

import random
import sys
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont

PRODUCTS = {
    "yogur": {
        "title": "Yogur desnatado ligero sabor limón",
        "rows": [
            ("Valor energético", "187 kJ / 44 kcal"),
            ("Grasas", "0,1 g"),
            ("  de las cuales saturadas", "0,1 g"),
            ("Hidratos de carbono", "6,5 g"),
            ("  de los cuales azúcares", "6,2 g"),
            ("Proteínas", "4,1 g"),
            ("Sal", "0,12 g"),
        ],
        "extra": "1 yogur = 125 g",
    },
    "leche": {
        "title": "Leche semidesnatada",
        "per": "100 ml",
        "rows": [
            ("Valor energético", "192 kJ / 46 kcal"),
            ("Grasas", "1,6 g"),
            ("  de las cuales saturadas", "1,1 g"),
            ("Hidratos de carbono", "4,7 g"),
            ("  de los cuales azúcares", "4,7 g"),
            ("Proteínas", "3,2 g"),
            ("Sal", "0,10 g"),
        ],
        "extra": "1 vaso = 200 ml",
    },
    "queso": {
        "title": "Queso fresco batido 0 %",
        "rows": [
            ("Valor energético", "192 kJ / 46 kcal"),
            ("Grasas", "0,2 g"),
            ("  de las cuales saturadas", "0,1 g"),
            ("Hidratos de carbono", "3,5 g"),
            ("  de los cuales azúcares", "3,5 g"),
            ("Proteínas", "8,0 g"),
            ("Sal", "0,18 g"),
        ],
        "extra": "Tarrina: 250 g",
    },
    "galletas": {
        "title": "Galletas integrales con avena",
        "rows": [
            ("Valor energético", "1850 kJ / 440 kcal"),
            ("Grasas", "14 g"),
            ("  de las cuales saturadas", "3,1 g"),
            ("Hidratos de carbono", "68 g"),
            ("  de los cuales azúcares", "19 g"),
            ("Fibra alimentaria", "6,4 g"),
            ("Proteínas", "7,5 g"),
            ("Sal", "0,68 g"),
        ],
        "extra": "Porción: 1 galleta (12 g)",
    },
}
FONTS = ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf"]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size, index=1 if bold and path.endswith(".ttc") else 0)
        except OSError:
            continue
    return ImageFont.load_default()


def make(kind: str = "yogur", seed: int = 4) -> bytes:
    spec = PRODUCTS[kind]
    random.seed(seed)
    w, h = 1000, 1200
    box = Image.new("RGB", (w, h), (236, 232, 222))  # cartón del envase
    d = ImageDraw.Draw(box)
    d.rectangle((60, 60, w - 60, h - 60), fill=(252, 251, 247), outline=(30, 30, 30), width=5)
    d.text((100, 100), "INFORMACIÓN NUTRICIONAL", font=font(46, True), fill=(20, 20, 20))
    d.text((100, 168), f"Valores medios por {spec.get('per', '100 g')}", font=font(34), fill=(40, 40, 40))
    d.line((100, 224, w - 100, 224), fill=(20, 20, 20), width=6)
    y = 250
    for label, value in spec["rows"]:
        small = label.startswith("  ")
        d.text((120 if small else 100, y), label.strip(), font=font(34 if not small else 30), fill=(30, 30, 30))
        right = font(34 if not small else 30, not small)
        d.text((w - 100 - d.textlength(value, font=right), y), value, font=right, fill=(20, 20, 20))
        y += 70
        d.line((100, y - 12, w - 100, y - 12), fill=(150, 150, 150), width=2)
    d.text((100, y + 20), spec["extra"], font=font(30), fill=(60, 60, 60))
    d.text((100, h - 190), spec["title"], font=font(36, True), fill=(40, 40, 40))
    d.text((100, h - 140), "Conservar en frío entre 1 y 6 °C", font=font(26), fill=(90, 90, 90))
    # Se hace «como foto»: ligero giro, desenfoque mínimo, mesa de fondo y ruido.
    canvas = Image.new("RGB", (1200, 1400), (88, 64, 44))
    photo = box.rotate(random.uniform(-2.5, 2.5), expand=True, fillcolor=(88, 64, 44), resample=Image.BICUBIC)
    canvas.paste(photo, ((1200 - photo.width) // 2, (1400 - photo.height) // 2))
    canvas = canvas.filter(ImageFilter.GaussianBlur(0.8))
    out = BytesIO()
    canvas.save(out, "JPEG", quality=84)
    return out.getvalue()


if __name__ == "__main__":
    kind, target = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("yogur", "etiqueta.jpg")
    data = make(kind)
    with open(target, "wb") as handle:
        handle.write(data)
    print(target, len(data) // 1024, "KB")

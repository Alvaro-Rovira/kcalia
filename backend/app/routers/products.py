"""Productos envasados: se lee la etiqueta de una foto, el usuario la revisa y queda guardada."""

from functools import lru_cache

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import barcode as barcodes
from .. import services
from ..ai import AiClient, finalize_label
from ..db import get_db
from ..deps import get_ai_client, require_approved_user, require_user
from ..models import Product, ProductImage, User, utcnow
from ..schemas import ProductIn, ProductPatch
from ..security import RateLimit
from ..usage import check_ai_budget, run_ai

router = APIRouter(prefix="/api/products", tags=["productos"], dependencies=[Depends(require_approved_user)])

MAX_IMAGE_BYTES = 6 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
# Consultas a Open Food Facts por usuario y día (las que salen a la red; la caché no cuenta).
barcode_limit = RateLimit(limit=150, window=86400)


@lru_cache
def get_barcode_http() -> httpx.Client:
    return httpx.Client(timeout=barcodes.TIMEOUT)


def _clean_barcode(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    code = barcodes.normalize_code(raw)
    if code is None:
        raise HTTPException(422, "Ese código de barras no es válido. Revisa los números.")
    return code


def _check_barcode_free(db: Session, code: str | None, own_id: int | None = None) -> None:
    if code is None:
        return
    other = db.scalar(select(Product).where(Product.barcode == code))
    if other is not None and other.id != own_id:
        raise HTTPException(409, f"Ya tienes guardado ese código de barras en «{other.name}».")


def _read_image(upload: UploadFile) -> tuple[bytes, str]:
    mime = (upload.content_type or "").lower()
    if mime not in IMAGE_TYPES:
        raise HTTPException(415, "Ese formato de imagen no me vale. Prueba con una foto JPG o PNG.")
    data = upload.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "La foto pesa demasiado. Prueba con una más pequeña.")
    if not data:
        raise HTTPException(422, "La foto está vacía.")
    return data, mime


def _get(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Ese producto ya no está guardado.")
    return product


@router.post("/scan")
def scan(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    ai: AiClient = Depends(get_ai_client),
    user: User = Depends(require_user),
) -> dict:
    """Lee la tabla nutricional de la foto. No guarda nada: devuelve un borrador para que el usuario lo revise."""
    data, mime = _read_image(image)
    check_ai_budget(db, user)
    draft = run_ai(db, "vision", lambda: ai.analyze_label(data, mime))
    if not draft.is_label:
        return {
            "status": "clarify",
            "question": "No veo una tabla de información nutricional en la foto. Enfoca la parte de atrás del "
            "envase, donde pone las calorías y los macros, con buena luz.",
        }
    return {"status": "ok", "draft": finalize_label(draft)}


@router.get("/barcode/{code}")
def by_barcode(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    http: httpx.Client = Depends(get_barcode_http),
) -> dict:
    """Busca un código: primero en tus productos, luego en la caché y, si hace falta, en Open Food Facts."""
    clean = barcodes.normalize_code(code)
    if clean is None:
        raise HTTPException(422, "Ese código de barras no es válido. Revisa los números.")
    own = db.scalar(select(Product).where(Product.barcode == clean))
    if own is not None:
        return {"status": "saved", "product": services.product_dict(own)}
    cached = db.get(barcodes.BarcodeCache, clean)
    if cached is None and not barcode_limit.allow(str(user.id)):
        raise HTTPException(
            429, "Has buscado muchos códigos hoy. Mañana podrás seguir; mientras, usa la foto de la etiqueta."
        )
    try:
        return {**barcodes.lookup(db, clean, http), "code": clean}
    except barcodes.LookupError_:
        return {"status": "unavailable", "code": clean}


@router.get("")
def list_products(db: Session = Depends(get_db)) -> dict:
    usage = services.slot_usage(db)[1]
    return {"products": [services.product_dict(p, usage.get(p.id)) for p in services.all_products(db)]}


@router.post("", status_code=201)
def create_product(
    data: str = Form(...), image: UploadFile | None = File(default=None), db: Session = Depends(get_db)
) -> dict:
    try:
        body = ProductIn.model_validate_json(data)
    except ValidationError as exc:
        fields = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc")})
        raise HTTPException(
            422, f"Hay cifras que no cuadran ({', '.join(fields)}). Revísalas y prueba otra vez."
        ) from exc

    product = Product(**body.model_dump())
    product.barcode = _clean_barcode(body.barcode)
    _check_barcode_free(db, product.barcode)
    product.alias = (product.alias or product.name).strip().lower()
    product.name = product.name.strip()
    db.add(product)
    db.flush()
    if image is not None:
        blob, mime = _read_image(image)
        db.add(ProductImage(product_id=product.id, mime=mime, data=blob))
        product.has_image = True
    db.commit()
    return services.product_dict(product)


@router.patch("/{product_id}")
def update_product(product_id: int, body: ProductPatch, db: Session = Depends(get_db)) -> dict:
    product = _get(db, product_id)
    changes = body.model_dump(exclude_unset=True)
    if "barcode" in changes:
        changes["barcode"] = _clean_barcode(changes["barcode"])
        _check_barcode_free(db, changes["barcode"], product.id)
    for key, value in changes.items():
        if key in ("name", "alias", "unit_label") and isinstance(value, str):
            value = value.strip()
        setattr(product, key, value)
    product.alias = (product.alias or product.name).strip().lower()
    if product.protein100 + product.carbs100 + product.fat100 > 105:
        raise HTTPException(422, "Proteínas, hidratos y grasas por 100 g no pueden sumar más de 100 g.")
    db.commit()
    return services.product_dict(product)


@router.put("/{product_id}/image")
def replace_image(product_id: int, image: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    product = _get(db, product_id)
    blob, mime = _read_image(image)
    row = db.get(ProductImage, product_id)
    if row is None:
        db.add(ProductImage(product_id=product_id, mime=mime, data=blob))
    else:
        row.mime, row.data = mime, blob
    product.has_image = True
    product.last_used_at = product.last_used_at or utcnow()
    db.commit()
    return services.product_dict(product)


@router.get("/{product_id}/image")
def get_image(product_id: int, db: Session = Depends(get_db)) -> Response:
    row = db.get(ProductImage, product_id)
    if row is None:
        raise HTTPException(404, "Este producto no tiene foto.")
    return Response(row.data, media_type=row.mime, headers={"Cache-Control": "private, max-age=86400"})


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)) -> dict:
    product = db.get(Product, product_id)
    if product is not None:
        image = db.get(ProductImage, product_id)
        if image is not None:
            db.delete(image)
        db.delete(product)
        db.commit()
    return {"ok": True}

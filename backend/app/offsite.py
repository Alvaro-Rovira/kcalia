"""Copia de seguridad fuera del servidor: sube la copia nocturna a un almacenamiento compatible con S3.

- Firma AWS SigV4 propia sobre httpx (sin boto3): sirve para AWS S3, Cloudflare R2, Backblaze B2, MinIO...
- Cifrado opcional con AES-256-GCM y una frase (BACKUP_ENCRYPTION_KEY), con la clave derivada por scrypt.
- Integridad: Content-MD5 (el almacenamiento rechaza la subida si no cuadra) y, después, se comprueba que el objeto
  guardado tiene el tamaño y el SHA-256 esperados.
- Retención: se conservan las BACKUP_REMOTE_KEEP copias más recientes del prefijo.

Sin destino configurado no hace nada: la app funciona igual y Ajustes lo indica.
"""

import base64
import hashlib
import hmac
import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .config import Settings

log = logging.getLogger("kcalia.offsite")

MAGIC = b"KCALIA-BK1"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


# ---------------------------------------------------------------- firma SigV4


def _hmac(key: bytes, text: str) -> bytes:
    return hmac.new(key, text.encode(), hashlib.sha256).digest()


def sign(
    method: str,
    url: str,
    headers: dict[str, str],
    payload_sha256: str,
    *,
    access_key: str,
    secret_key: str,
    region: str,
    now: datetime | None = None,
    service: str = "s3",
) -> dict[str, str]:
    """Cabeceras firmadas (Authorization, x-amz-date, x-amz-content-sha256 y host) para la petición."""
    now = now or datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    parsed = urlparse(url)
    all_headers = {k.lower(): v.strip() for k, v in headers.items()}
    all_headers["host"] = parsed.netloc
    all_headers["x-amz-date"] = amz_date
    all_headers["x-amz-content-sha256"] = payload_sha256
    signed = sorted(all_headers)
    canonical_headers = "".join(f"{name}:{all_headers[name]}\n" for name in signed)
    query = "&".join(
        sorted(
            f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}"
            for k, _, v in (pair.partition("=") for pair in parsed.query.split("&") if pair)
        )
    )
    canonical = "\n".join(
        [
            method,
            quote(parsed.path or "/", safe="/-_.~"),
            query,
            canonical_headers,
            ";".join(signed),
            payload_sha256,
        ]
    )
    scope = f"{day}/{region}/{service}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    key = _hmac(_hmac(_hmac(_hmac(f"AWS4{secret_key}".encode(), day), region), service), "aws4_request")
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    return {
        **{name: all_headers[name] for name in signed},
        "Authorization": f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={';'.join(signed)}, "
        f"Signature={signature}",
    }


# ---------------------------------------------------------------- cifrado


def _key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(passphrase.encode())


def encrypt(data: bytes, passphrase: str) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(12)
    return MAGIC + salt + nonce + AESGCM(_key(passphrase, salt)).encrypt(nonce, data, MAGIC)


def decrypt(blob: bytes, passphrase: str) -> bytes:
    if not blob.startswith(MAGIC):
        raise ValueError("No es una copia cifrada de Kcalia")
    salt, nonce = blob[len(MAGIC) : len(MAGIC) + 16], blob[len(MAGIC) + 16 : len(MAGIC) + 28]
    return AESGCM(_key(passphrase, salt)).decrypt(nonce, blob[len(MAGIC) + 28 :], MAGIC)


# ---------------------------------------------------------------- subida


@dataclass
class Result:
    ok: bool
    key: str = ""
    size: int = 0
    sha256: str = ""
    deleted: int = 0
    error: str = ""


def configured(settings: Settings) -> bool:
    return bool(
        settings.backup_remote_url
        and settings.backup_remote_bucket
        and settings.backup_remote_access_key
        and settings.backup_remote_secret_key
    )


class Remote:
    def __init__(self, settings: Settings, http: httpx.Client):
        self.s = settings
        self.http = http
        self.base = f"{settings.backup_remote_url.rstrip('/')}/{settings.backup_remote_bucket}"

    def _request(self, method: str, key: str = "", *, query: str = "", body: bytes = b"", headers: dict | None = None):
        url = f"{self.base}/{quote(key, safe='/-_.~')}" if key else f"{self.base}"
        if query:
            url += f"?{query}"
        signed = sign(
            method,
            url,
            headers or {},
            hashlib.sha256(body).hexdigest() if body else EMPTY_SHA256,
            access_key=self.s.backup_remote_access_key,
            secret_key=self.s.backup_remote_secret_key,
            region=self.s.backup_remote_region,
        )
        signed.pop("host", None)
        return self.http.request(method, url, content=body or None, headers=signed)

    def put(self, key: str, body: bytes, sha256: str) -> None:
        md5 = base64.b64encode(hashlib.md5(body).digest()).decode()  # noqa: S324 (lo exige S3 para Content-MD5)
        response = self._request(
            "PUT",
            key,
            body=body,
            headers={"Content-MD5": md5, "Content-Type": "application/octet-stream", "x-amz-meta-sha256": sha256},
        )
        if response.status_code >= 300:
            raise RuntimeError(f"la subida respondió {response.status_code}: {response.text[:200]}")

    def verify(self, key: str, size: int, sha256: str) -> None:
        response = self._request("HEAD", key)
        if response.status_code >= 300:
            raise RuntimeError(f"no encuentro la copia recién subida ({response.status_code})")
        remote_size = int(response.headers.get("content-length", -1))
        remote_sha = response.headers.get("x-amz-meta-sha256", "")
        if remote_size != size or remote_sha != sha256:
            raise RuntimeError("la copia subida no coincide con la local (tamaño o SHA-256)")

    def list(self) -> list[str]:
        prefix = quote(self.s.backup_remote_prefix, safe="")
        response = self._request("GET", query=f"list-type=2&prefix={prefix}")
        if response.status_code >= 300:
            raise RuntimeError(f"no puedo listar las copias ({response.status_code})")
        root = ET.fromstring(response.text)
        return sorted(el.text for el in root.iter() if el.tag.endswith("Key") and el.text)

    def delete(self, key: str) -> None:
        self._request("DELETE", key)


def upload(path: Path, settings: Settings, http: httpx.Client) -> Result:
    """Sube una copia local (ya comprimida), la verifica y aplica la retención."""
    if not configured(settings):
        return Result(ok=False, error="sin destino configurado")
    data = path.read_bytes()
    name = path.name
    if settings.backup_encryption_key:
        data = encrypt(data, settings.backup_encryption_key)
        name += ".enc"
    key = f"{settings.backup_remote_prefix}{name}"
    sha256 = hashlib.sha256(data).hexdigest()
    remote = Remote(settings, http)
    try:
        remote.put(key, data, sha256)
        remote.verify(key, len(data), sha256)
        deleted = 0
        keys = [k for k in remote.list() if k.rsplit("/", 1)[-1].startswith("kcalia-")]
        for old in keys[: max(0, len(keys) - settings.backup_remote_keep)]:
            remote.delete(old)
            deleted += 1
    except (httpx.HTTPError, RuntimeError, ET.ParseError) as exc:
        log.warning("Fallo al subir la copia externa: %s", exc)
        return Result(ok=False, key=key, error=str(exc)[:300])
    log.info("Copia externa subida: %s (%s bytes)", key, len(data))
    return Result(ok=True, key=key, size=len(data), sha256=sha256, deleted=deleted)

"""Web Push sin dependencias pesadas: cifrado RFC 8291 (aes128gcm) y autenticación VAPID (RFC 8292).

Solo usa `cryptography`. El cifrado se prueba contra el vector de ejemplo de la propia RFC 8291.
"""

import base64
import json
import os
import struct
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

RECORD_SIZE = 4096


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def _public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def private_key_from_b64(text: str) -> ec.EllipticCurvePrivateKey:
    return ec.derive_private_key(int.from_bytes(b64url_decode(text), "big"), ec.SECP256R1())


def generate_vapid_keys() -> tuple[str, str]:
    """(privada, pública) en base64url, como las esperan VAPID_PRIVATE_KEY y VAPID_PUBLIC_KEY."""
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    return b64url(private), b64url(_public_bytes(key.public_key()))


def encrypt(
    plaintext: bytes,
    ua_public: bytes,
    auth_secret: bytes,
    *,
    sender_key: ec.EllipticCurvePrivateKey | None = None,
    salt: bytes | None = None,
) -> bytes:
    """Cuerpo cifrado aes128gcm para una suscripción (claves `p256dh` y `auth` del navegador).

    `sender_key` y `salt` solo se fijan en las pruebas (vector de la RFC); en uso real son aleatorios.
    """
    sender_key = sender_key or ec.generate_private_key(ec.SECP256R1())
    salt = salt or os.urandom(16)
    as_public = _public_bytes(sender_key.public_key())
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    shared = sender_key.exchange(ec.ECDH(), ua_key)
    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    # Un solo registro: el texto, el delimitador de último registro (0x02) y sin relleno.
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)
    header = salt + struct.pack("!I", RECORD_SIZE) + bytes([len(as_public)]) + as_public
    return header + ciphertext


def vapid_authorization(
    endpoint: str, private_key: str, public_key: str, subject: str, now: float | None = None
) -> str:
    """Cabecera Authorization «vapid t=…, k=…» con un JWT ES256 válido 12 horas."""
    url = urlparse(endpoint)
    claims = {"aud": f"{url.scheme}://{url.netloc}", "exp": int((now or time.time()) + 12 * 3600), "sub": subject}
    header = {"typ": "JWT", "alg": "ES256"}

    def part(value: dict) -> str:
        return b64url(json.dumps(value, separators=(",", ":")).encode())

    signing_input = f"{part(header)}.{part(claims)}"
    der = private_key_from_b64(private_key).sign(signing_input.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"vapid t={signing_input}.{b64url(signature)}, k={public_key}"


@dataclass
class SendResult:
    ok: bool
    status: int
    # La suscripción ya no existe (404 o 410): hay que borrarla.
    gone: bool


def send(
    endpoint: str,
    p256dh: str,
    auth: str,
    payload: dict,
    *,
    private_key: str,
    public_key: str,
    subject: str,
    http: httpx.Client,
    ttl: int = 6 * 3600,
) -> SendResult:
    body = encrypt(json.dumps(payload, ensure_ascii=False).encode(), b64url_decode(p256dh), b64url_decode(auth))
    headers = {
        "TTL": str(ttl),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "Urgency": "normal",
        "Authorization": vapid_authorization(endpoint, private_key, public_key, subject),
    }
    try:
        response = http.post(endpoint, content=body, headers=headers)
    except httpx.HTTPError:
        return SendResult(ok=False, status=0, gone=False)
    return SendResult(
        ok=response.status_code < 300, status=response.status_code, gone=response.status_code in (404, 410)
    )

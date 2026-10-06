"""Web Push: cifrado contra el vector de ejemplo de la RFC 8291 (apéndice A) y firma VAPID verificable."""

import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.webpush import b64url, b64url_decode, encrypt, generate_vapid_keys, private_key_from_b64, vapid_authorization

# RFC 8291, apéndice A.
PLAINTEXT = b"When I grow up, I want to be a watermelon"
AS_PRIVATE = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
UA_PRIVATE = "q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94"
UA_PUBLIC = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
SALT = "DGv6ra1nlYgDCS1FRnbzlw"
EXPECTED = (
    "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_"
    "yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
)


def test_cifrado_igual_que_el_ejemplo_de_la_rfc_8291():
    body = encrypt(
        PLAINTEXT,
        b64url_decode(UA_PUBLIC),
        b64url_decode(AUTH),
        sender_key=private_key_from_b64(AS_PRIVATE),
        salt=b64url_decode(SALT),
    )
    assert b64url(body) == EXPECTED


def test_el_navegador_puede_descifrarlo():
    """Lo que haría el navegador con su clave privada, con claves y sal aleatorias."""
    ua_key = private_key_from_b64(UA_PRIVATE)
    body = encrypt(PLAINTEXT, b64url_decode(UA_PUBLIC), b64url_decode(AUTH))
    salt, sender = body[:16], body[21:86]
    shared = ua_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), sender))

    def hkdf(s, ikm, info, n):
        return HKDF(algorithm=hashes.SHA256(), length=n, salt=s, info=info).derive(ikm)

    ikm = hkdf(b64url_decode(AUTH), shared, b"WebPush: info\x00" + b64url_decode(UA_PUBLIC) + sender, 32)
    cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    assert AESGCM(cek).decrypt(nonce, body[86:], None) == PLAINTEXT + b"\x02"


def test_firma_vapid_valida():
    private, public = generate_vapid_keys()
    header = vapid_authorization(
        "https://push.example.net/wpush/v2/abc", private, public, "mailto:admin@example.com", now=1_000_000
    )
    token, key = header.removeprefix("vapid t=").split(", k=")
    assert key == public
    head, claims, signature = token.split(".")
    assert json.loads(b64url_decode(claims)) == {
        "aud": "https://push.example.net",
        "exp": 1_000_000 + 43_200,
        "sub": "mailto:admin@example.com",
    }
    raw = b64url_decode(signature)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b64url_decode(public))
    public_key.verify(der, f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))  # lanza si no es válida

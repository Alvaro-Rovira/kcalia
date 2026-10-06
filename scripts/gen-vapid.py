#!/usr/bin/env python3
"""Genera las claves VAPID de las notificaciones Web Push y las guarda en .env sin mostrarlas.

    python scripts/gen-vapid.py --env-file .env            # en local (necesita `cryptography`)

En el servidor, con el Python del contenedor (que ya tiene `cryptography`) y sin que la clave pase por la pantalla:

    cd /opt/kcalia && docker compose exec -T app python - --stdout < scripts/gen-vapid.py >> .env

Si .env ya tiene una VAPID_PRIVATE_KEY no se cambia nada: cambiarla invalidaría las suscripciones existentes.
"""

import argparse
import base64
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate() -> tuple[str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    private = b64url(key.private_numbers().private_value.to_bytes(32, "big"))
    public = b64url(
        key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )
    return private, public


def write_env(path: Path, private: str, public: str, subject: str | None) -> bool:
    text = path.read_text() if path.exists() else ""
    current = re.search(r"^VAPID_PRIVATE_KEY=(.+)$", text, re.M)
    if current and current.group(1).strip():
        return False
    values = {"VAPID_PUBLIC_KEY": public, "VAPID_PRIVATE_KEY": private}
    if subject:
        values["VAPID_SUBJECT"] = subject
    for name, value in values.items():
        line = f"{name}={value}"
        if re.search(rf"^{name}=.*$", text, re.M):
            text = re.sub(rf"^{name}=.*$", line, text, flags=re.M)
        else:
            text = text.rstrip("\n") + ("\n" if text else "") + line + "\n"
    path.write_text(text)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claves VAPID para las notificaciones de Kcalia.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--env-file", type=Path, help="fichero .env donde guardarlas (no se muestran)")
    target.add_argument(
        "--stdout", action="store_true", help="escribirlas como líneas de .env (para redirigir a un fichero)"
    )
    parser.add_argument("--subject", help="contacto para los servicios de push, p. ej. mailto:tu@correo.es")
    args = parser.parse_args(argv)

    private, public = generate()
    if args.stdout:
        print(f"VAPID_PUBLIC_KEY={public}")
        print(f"VAPID_PRIVATE_KEY={private}")
        if args.subject:
            print(f"VAPID_SUBJECT={args.subject}")
        return 0
    if write_env(args.env_file, private, public, args.subject):
        print(f"Claves VAPID guardadas en {args.env_file} (no se muestran). Reinicia la app para usarlas.")
    else:
        print(f"{args.env_file} ya tiene claves VAPID: no se cambian (invalidaría las suscripciones).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

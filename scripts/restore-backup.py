#!/usr/bin/env python3
"""Convierte una copia de seguridad (local o descargada del almacenamiento externo) en una base de datos lista.

    python scripts/restore-backup.py kcalia-2026-10-06.db.gz kcalia.db
    python scripts/restore-backup.py kcalia-2026-10-06.db.gz.enc kcalia.db     # pide la frase sin mostrarla

Las copias cifradas (.enc) necesitan `cryptography` y la frase de BACKUP_ENCRYPTION_KEY. Comprueba que el resultado
es una base SQLite íntegra antes de dar el trabajo por hecho. Cómo ponerla en marcha: README, «Copias de seguridad».
"""

import argparse
import getpass
import gzip
import os
import sqlite3
import sys
from pathlib import Path

MAGIC = b"KCALIA-BK1"


def decrypt(blob: bytes, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    if not blob.startswith(MAGIC):
        raise ValueError("no es una copia cifrada de Kcalia")
    salt, nonce = blob[len(MAGIC) : len(MAGIC) + 16], blob[len(MAGIC) + 16 : len(MAGIC) + 28]
    key = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(passphrase.encode())
    return AESGCM(key).decrypt(nonce, blob[len(MAGIC) + 28 :], MAGIC)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restaura una copia de seguridad de Kcalia en un fichero .db")
    parser.add_argument("backup", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        print(f"{args.output} ya existe: elige otro nombre para no pisarlo.", file=sys.stderr)
        return 1
    blob = args.backup.read_bytes()
    if blob.startswith(MAGIC):
        passphrase = os.environ.get("BACKUP_ENCRYPTION_KEY") or getpass.getpass("Frase de cifrado: ")
        blob = decrypt(blob, passphrase)
    args.output.write_bytes(gzip.decompress(blob))
    conn = sqlite3.connect(args.output)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        meals = conn.execute("SELECT COUNT(*) FROM meals").fetchone()[0]
    finally:
        conn.close()
    if result != "ok":
        print(f"La base restaurada no está íntegra: {result}", file=sys.stderr)
        return 2
    print(f"Base restaurada en {args.output}: íntegra, {meals} comidas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

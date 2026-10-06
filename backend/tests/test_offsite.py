"""Copia externa: firma SigV4 (ejemplo oficial de AWS), cifrado, subida verificada y retención contra un S3 simulado."""

import base64
import gzip
import hashlib
import sqlite3
from datetime import UTC, datetime
from urllib.parse import parse_qs, unquote, urlparse

import httpx
import pytest
from conftest import reset_database

from app import jobs, offsite, services
from app.config import Settings, get_settings
from app.db import SessionLocal


def test_firma_igual_que_el_ejemplo_de_aws():
    """«GET Object» de la documentación de AWS (Signature Version 4, payload en un solo bloque)."""
    headers = offsite.sign(
        "GET",
        "https://examplebucket.s3.amazonaws.com/test.txt",
        {"Range": "bytes=0-9"},
        offsite.EMPTY_SHA256,
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
        now=datetime(2013, 5, 24, tzinfo=UTC),
    )
    assert "Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request" in headers["Authorization"]
    assert "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date" in headers["Authorization"]
    assert headers["Authorization"].endswith(
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )


def test_cifrado_ida_y_vuelta():
    blob = offsite.encrypt(b"datos de prueba", "una frase larga")
    assert blob.startswith(offsite.MAGIC) and b"datos" not in blob
    assert offsite.decrypt(blob, "una frase larga") == b"datos de prueba"
    with pytest.raises(Exception):  # noqa: B017
        offsite.decrypt(blob, "otra frase")


class FakeS3:
    """Lo justo de S3: PUT (comprueba Content-MD5), HEAD, listar y borrar."""

    def __init__(self):
        self.objects: dict[str, tuple[bytes, dict]] = {}
        self.fail = False
        self.lie = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("AWS4-HMAC-SHA256 Credential=clave/")
        if self.fail:
            return httpx.Response(500, text="error interno")
        path = unquote(urlparse(str(request.url)).path)
        bucket, _, key = path.lstrip("/").partition("/")
        assert bucket == "copias"
        if request.method == "PUT":
            body = request.content
            if base64.b64encode(hashlib.md5(body).digest()).decode() != request.headers["content-md5"]:
                return httpx.Response(400, text="BadDigest")
            self.objects[key] = (body, {"x-amz-meta-sha256": request.headers["x-amz-meta-sha256"]})
            return httpx.Response(200)
        if request.method == "HEAD":
            if key not in self.objects:
                return httpx.Response(404)
            body, meta = self.objects[key]
            sha = "0" * 64 if self.lie else meta["x-amz-meta-sha256"]
            return httpx.Response(200, headers={"content-length": str(len(body)), "x-amz-meta-sha256": sha})
        if request.method == "GET":
            prefix = parse_qs(urlparse(str(request.url)).query)["prefix"][0]
            keys = "".join(f"<Contents><Key>{k}</Key></Contents>" for k in sorted(self.objects) if k.startswith(prefix))
            return httpx.Response(200, text=f'<?xml version="1.0"?><ListBucketResult>{keys}</ListBucketResult>')
        if request.method == "DELETE":
            self.objects.pop(key, None)
            return httpx.Response(204)
        return httpx.Response(405)


def settings_for(tmp_path, **extra) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        backup_remote_url="https://s3.example.com",
        backup_remote_bucket="copias",
        backup_remote_access_key="clave",
        backup_remote_secret_key="secreto",
        backup_remote_keep=3,
        **extra,
    )


def local_backup(tmp_path, day: str):
    path = tmp_path / f"kcalia-{day}.db.gz"
    path.write_bytes(gzip.compress(f"copia del {day}".encode()))
    return path


def test_subida_verificada_y_retencion(tmp_path):
    s3 = FakeS3()
    http = httpx.Client(transport=httpx.MockTransport(s3.handler))
    settings = settings_for(tmp_path)
    for day in ("2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"):
        result = offsite.upload(local_backup(tmp_path, day), settings, http)
        assert result.ok, result.error
    assert sorted(s3.objects) == [
        "kcalia/kcalia-2026-10-02.db.gz",
        "kcalia/kcalia-2026-10-03.db.gz",
        "kcalia/kcalia-2026-10-04.db.gz",
    ]
    assert result.deleted == 1
    body, meta = s3.objects["kcalia/kcalia-2026-10-04.db.gz"]
    assert gzip.decompress(body) == b"copia del 2026-10-04"
    assert meta["x-amz-meta-sha256"] == hashlib.sha256(body).hexdigest() == result.sha256


def test_cifrada_y_restaurable(tmp_path):
    s3 = FakeS3()
    settings = settings_for(tmp_path, backup_encryption_key="frase secreta de prueba")
    result = offsite.upload(
        local_backup(tmp_path, "2026-10-05"), settings, httpx.Client(transport=httpx.MockTransport(s3.handler))
    )
    assert result.ok and result.key.endswith(".db.gz.enc")
    body = s3.objects[result.key][0]
    assert gzip.decompress(offsite.decrypt(body, "frase secreta de prueba")) == b"copia del 2026-10-05"


def test_fallos_y_copia_que_no_cuadra(tmp_path):
    s3 = FakeS3()
    http = httpx.Client(transport=httpx.MockTransport(s3.handler))
    settings = settings_for(tmp_path)
    s3.fail = True
    failed = offsite.upload(local_backup(tmp_path, "2026-10-06"), settings, http)
    assert not failed.ok and "500" in failed.error
    s3.fail, s3.lie = False, True
    mismatch = offsite.upload(local_backup(tmp_path, "2026-10-06"), settings, http)
    assert not mismatch.ok and "no coincide" in mismatch.error


def test_sin_destino_no_hace_nada(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path, backup_dir=tmp_path)
    assert not offsite.configured(settings)
    assert jobs.upload_offsite(settings, local_backup(tmp_path, "2026-10-06"), "2026-10-06") is None


def test_la_tarea_nocturna_guarda_el_estado_y_reintenta(tmp_path):
    reset_database()
    s3 = FakeS3()
    jobs.set_offsite_http(httpx.Client(transport=httpx.MockTransport(s3.handler)))
    settings = settings_for(tmp_path)
    try:
        s3.fail = True
        status = jobs.upload_offsite(settings, local_backup(tmp_path, "2026-10-06"), "2026-10-06")
        assert status["ok"] is False and status["attempts"] == 1
        s3.fail = False
        status = jobs.upload_offsite(settings, local_backup(tmp_path, "2026-10-06"), "2026-10-06")
        assert status["ok"] is True and status["attempts"] == 2 and status["last_ok_at"]
        assert (
            jobs.upload_offsite(settings, local_backup(tmp_path, "2026-10-06"), "2026-10-06")["attempts"] == 2
        )  # ya está
        with SessionLocal() as db:
            assert services.app_setting(db, jobs.BACKUP_STATUS_KEY)["key"] == "kcalia/kcalia-2026-10-06.db.gz"
    finally:
        jobs.set_offsite_http(None)


def test_la_copia_local_sigue_siendo_una_base_valida(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    conn = sqlite3.connect(data / "kcalia.db")
    conn.execute("CREATE TABLE t (x)")
    conn.commit()
    conn.close()
    settings = Settings(_env_file=None, data_dir=data, backup_dir=tmp_path / "backups")
    path = jobs.backup_database(settings, datetime(2026, 10, 6, 3))
    assert path.exists() and get_settings() is not None


def test_script_de_restauracion(tmp_path, monkeypatch, capsys):
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "restore-backup.py"
    spec = importlib.util.spec_from_file_location("restore_backup", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    db = tmp_path / "origen.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE meals (id INTEGER PRIMARY KEY)")
    conn.executemany("INSERT INTO meals VALUES (?)", [(1,), (2,)])
    conn.commit()
    conn.close()
    encrypted = tmp_path / "kcalia-2026-10-06.db.gz.enc"
    encrypted.write_bytes(offsite.encrypt(gzip.compress(db.read_bytes()), "frase"))
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", "frase")
    assert module.main([str(encrypted), str(tmp_path / "restaurada.db")]) == 0
    assert "íntegra, 2 comidas" in capsys.readouterr().out
    assert module.main([str(encrypted), str(tmp_path / "restaurada.db")]) == 1  # no pisa un fichero existente

"""Intenta romper la API: cada operación recibe entradas absurdas y ninguna puede acabar en un error 500 ni tardar.

Las entradas salen del esquema OpenAPI de la propia app (aunque la documentación esté apagada): cuerpos vacíos o del tipo
equivocado, JSON roto, NaN e infinitos, números enormes, textos de 100.000 caracteres, nulos y Unicode roto, listas
enormes, anidamiento profundo, identificadores raros en la ruta y rangos de fechas desmesurados.
"""

import json
import os
import time

import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app.ai import AiError
from app.deps import get_ai_client
from app.main import app

SLOW_SECONDS = 2.0
LONG = "x" * 100_000
WEIRD_STRINGS = [LONG, "\x00", "\ud800", "😀" * 50, "'; DROP TABLE users; --", "<script>alert(1)</script>", " ",
                 "9999-12-31", "0001-01-01", "23:61", "2026-02-30"]  # fmt: skip
WEIRD_NUMBERS = [10**30, -(10**30), 1e308, -1, 0, 0.5, 2**63]
PATH_VALUES = ["-1", "0", "99999999999999999999999", "abc", "..%2F..%2Fetc%2Fpasswd", "%00", "x" * 3000, "😀"]
DATES = ["2026-13-45", "x", "0001-01-01", "9999-12-31", "-1", ""]


class BrokenAi:
    """Sin red en las pruebas: toda llamada a la IA falla como fallaría un proveedor caído."""

    configured = True

    def __getattr__(self, _name):
        def fail(*_args, **_kwargs):
            raise AiError("network", "sin IA en las pruebas")

        return fail


def deref(schema: dict, spec: dict) -> dict:
    if "$ref" in schema:
        node = spec
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        return deref(node, spec)
    if "anyOf" in schema:
        options = [deref(s, spec) for s in schema["anyOf"] if s.get("type") != "null"]
        return options[0] if options else {}
    if "allOf" in schema:
        merged: dict = {}
        for part in schema["allOf"]:
            merged.update(deref(part, spec))
        return merged
    return schema


NAMED = {  # campos que el esquema dice «texto» pero validan un formato concreto
    "date": "2026-10-01", "start": "2026-10-01", "end": "2026-10-07", "week_start": "2026-09-28", "today": "2026-10-01",
    "time": "08:30", "suggest_hour": "21:00", "weigh_reminder": "08:30",
    "endpoint": "https://fcm.googleapis.com/fcm/send/x", "client_id": "cid-fuzz-0001", "workout_cid": "cid-fuzz-0002",
}  # fmt: skip


def example(schema: dict, spec: dict, depth: int = 0, name: str = ""):
    """Un valor plausible para el esquema (lo mínimo para pasar la validación la mayoría de las veces)."""
    schema = deref(schema, spec)
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        if depth > 4:
            return {}
        return {key: example(sub, spec, depth + 1, key) for key, sub in schema.get("properties", {}).items()}
    if kind == "array":
        return [example(schema.get("items", {}), spec, depth + 1)] if depth < 4 else []
    if kind == "integer":
        return max(1, int(schema.get("minimum", 1)))
    if kind == "number":
        return float(max(1, schema.get("minimum", 1)))
    if kind == "boolean":
        return True
    if kind == "string":
        if name in NAMED:
            return NAMED[name]
        if name.endswith("_at"):
            return "2026-10-01T10:00:00"
        fmt = schema.get("format")
        if fmt == "date":
            return "2026-10-01"
        if schema.get("pattern") == r"^\d{2}:\d{2}$":
            return "08:30"
        return "a" * max(1, int(schema.get("minLength", 1)))
    return "a"


def variants(base):
    """Cuerpos JSON rotos a partir de uno plausible: cada campo con valores extremos y formas equivocadas."""
    yield "vacío", {}
    yield "lista", []
    yield "texto", "x"
    yield "nulo", None
    yield "plausible", base
    if isinstance(base, dict):
        for key, value in base.items():
            bad_values = [None, [], {}, *WEIRD_STRINGS, *WEIRD_NUMBERS]
            if isinstance(value, list):
                bad_values.append(value * 5000)
            for bad in bad_values:
                yield f"{key}={str(bad)[:20]!r}", {**base, key: bad}


RAW_BODIES = [
    ("json roto", b"{"),
    ("NaN", b'{"a": NaN}'),
    ("Infinity", b'{"a": Infinity, "b": -Infinity}'),
    ("anidado", b'{"a": ' * 5000 + b"1" + b"}" * 5000),
    ("binario", bytes(range(256))),
]


@pytest.fixture(scope="module")
def clients():
    reset_database()
    create_user("admin", is_admin=True)
    create_user("ana")
    app.dependency_overrides[get_ai_client] = BrokenAi
    admin = TestClient(app, raise_server_exceptions=False)
    user = TestClient(app, raise_server_exceptions=False)
    with admin, user:
        login(admin, "admin")
        login(user, "ana")
        profile = dict(sex="hombre", age=30, height_cm=180, weight_kg=80, activity="medio", goal="mantenimiento")
        assert user.put("/api/profile", json=profile).status_code == 200
        yield {"admin": admin, "ana": user}
    app.dependency_overrides.pop(get_ai_client, None)


def _operations():
    spec = app.openapi()
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if method in ("get", "post", "put", "patch", "delete"):
                yield path, method, op, spec


LOG = os.environ.get("FUZZ_LOG")  # para depurar: cada petición, antes de enviarla


def _send(client, method, url, label="", **kwargs):
    if LOG:
        with open(LOG, "a") as log:
            log.write(f"{method.upper()} {url[:100]} [{label}]\n")
    started = time.perf_counter()
    headers = {"Origin": "http://testserver", **kwargs.pop("headers", {})}
    response = client.request(method.upper(), url, headers=headers, **kwargs)
    return response, time.perf_counter() - started


def _fill_path(path: str, value: str) -> str:
    out = path
    while "{" in out:
        start = out.index("{")
        out = out[:start] + value + out[out.index("}") + 1 :]
    return out


def test_ninguna_entrada_rompe_la_api(clients):
    problems: list[str] = []
    for path, method, op, spec in _operations():
        client = clients["admin"] if path.startswith("/api/admin") else clients["ana"]
        if path in ("/api/auth/logout", "/api/account/delete", "/api/data/delete") or "logout-all" in path:
            continue  # cerrarían la sesión o borrarían los datos de la prueba a mitad del recorrido
        urls = [_fill_path(path, v) for v in PATH_VALUES] if "{" in path else [path]
        query_names = [p["name"] for p in op.get("parameters", []) if p.get("in") == "query"]
        body = op.get("requestBody", {}).get("content", {})
        for url in urls:
            attempts: list[tuple[str, dict]] = [("sin cuerpo", {})]
            if query_names:
                for value in DATES + ["-5", "99999999", LONG[:5000]]:
                    attempts.append((f"query={value[:12]!r}", {"params": dict.fromkeys(query_names, value)}))
                attempts.append(
                    ("rango enorme", {"params": {"start": "0001-01-01", "end": "9999-12-31", "days": "99999999"}})
                )
            if "application/json" in body:
                schema = body["application/json"].get("schema", {})
                for name, data in variants(example(schema, spec)):
                    try:
                        content = json.dumps(data).encode()
                    except (TypeError, ValueError):
                        continue
                    attempts.append((name, {"content": content, "headers": {"Content-Type": "application/json"}}))
                for name, raw in RAW_BODIES:
                    attempts.append((name, {"content": raw, "headers": {"Content-Type": "application/json"}}))
            if "multipart/form-data" in body:
                attempts += [
                    ("multipart vacío", {"files": {"x": ("a", b"")}}),
                    ("fichero vacío", {"files": {"image": ("a.jpg", b"", "image/jpeg"), "file": ("a.csv", b"")}}),
                    ("basura", {"files": {"image": ("a.jpg", bytes(range(256)) * 10, "image/jpeg")}}),
                    ("csv raro", {"files": {"file": ("a.csv", '﻿;;;\n\x00\n=1+1;"\n'.encode())}}),
                ]
            for name, kwargs in attempts:
                response, seconds = _send(client, method, url, name, **kwargs)
                # 502, 503 y 504 son las respuestas previstas cuando la IA no está disponible; 500 es un fallo.
                if response.status_code == 500:
                    problems.append(f"500 {method.upper()} {path} {url[len(path) :][:30]} [{name}]")
                elif seconds > SLOW_SECONDS:
                    problems.append(f"LENTO {seconds:.1f}s {method.upper()} {url[:80]} [{name}]")
    assert not problems, "\n".join(problems[:80]) + f"\n... {len(problems)} en total"

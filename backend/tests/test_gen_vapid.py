"""scripts/gen-vapid.py: guarda las claves sin mostrarlas y nunca pisa unas existentes."""

import importlib.util
from pathlib import Path

from app.webpush import b64url_decode, private_key_from_b64

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gen-vapid.py"
spec = importlib.util.spec_from_file_location("gen_vapid", SCRIPT)
gen_vapid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_vapid)


def read(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def test_guarda_claves_validas_sin_mostrarlas(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("DOMAIN=kcalia.example\nVAPID_PUBLIC_KEY=\nVAPID_PRIVATE_KEY=\n")
    gen_vapid.main(["--env-file", str(env), "--subject", "mailto:yo@example.com"])
    values = read(env)
    output = capsys.readouterr().out
    assert values["DOMAIN"] == "kcalia.example" and values["VAPID_SUBJECT"] == "mailto:yo@example.com"
    assert values["VAPID_PRIVATE_KEY"] not in output and values["VAPID_PUBLIC_KEY"] not in output
    assert len(b64url_decode(values["VAPID_PUBLIC_KEY"])) == 65
    private_key_from_b64(values["VAPID_PRIVATE_KEY"])  # es una clave P-256 válida


def test_no_pisa_claves_existentes(tmp_path):
    env = tmp_path / ".env"
    env.write_text("VAPID_PUBLIC_KEY=pub\nVAPID_PRIVATE_KEY=priv\n")
    gen_vapid.main(["--env-file", str(env)])
    assert read(env) == {"VAPID_PUBLIC_KEY": "pub", "VAPID_PRIVATE_KEY": "priv"}

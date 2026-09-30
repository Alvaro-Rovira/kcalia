import base64
import hashlib

from app.spa import render_index

INDEX = """<!doctype html><html><head>
<meta property="og:image" content="__ORIGIN__/og-image.png" />
<script src="/theme.js"></script>
<link rel="stylesheet" crossorigin href="/assets/index-abc123.css">
</head><body><div id="root"></div><script type="module" src="/assets/index-xyz.js"></script></body></html>"""


def make(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(INDEX)
    (tmp_path / "theme.js").write_text("document.documentElement.dataset.theme='dark'")
    (tmp_path / "assets" / "index-abc123.css").write_text("body{margin:0}")
    (tmp_path / "assets" / "geist-latin-wght-normal-Bg1x.woff2").write_bytes(b"font")
    return tmp_path


def test_pone_en_linea_el_css_y_el_tema(tmp_path):
    out = render_index(make(tmp_path), "https://kcalia.example")
    assert "<style>body{margin:0}</style>" in out.html
    assert "/assets/index-abc123.css" not in out.html
    assert "<script>document.documentElement.dataset.theme='dark'</script>" in out.html
    assert 'src="/theme.js"' not in out.html
    # El script del módulo principal sigue siendo externo.
    assert '<script type="module" src="/assets/index-xyz.js">' in out.html


def test_el_hash_de_la_csp_corresponde_al_script(tmp_path):
    out = render_index(make(tmp_path), "")
    digest = hashlib.sha256(b"document.documentElement.dataset.theme='dark'").digest()
    assert out.script_hash == "sha256-" + base64.b64encode(digest).decode()


def test_dominio_y_precarga_de_fuente(tmp_path):
    out = render_index(make(tmp_path), "https://kcalia.example")
    assert 'content="https://kcalia.example/og-image.png"' in out.html
    assert "__ORIGIN__" not in out.html
    assert 'rel="preload" href="/assets/geist-latin-wght-normal-Bg1x.woff2" as="font"' in out.html


def test_sin_theme_js_no_hay_hash(tmp_path):
    make(tmp_path)
    (tmp_path / "theme.js").unlink()
    out = render_index(tmp_path, "")
    assert out.script_hash is None
    assert '<script src="/theme.js"></script>' in out.html

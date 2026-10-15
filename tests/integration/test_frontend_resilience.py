"""Que un celular con señal floja o con archivos viejos en la caché no se quede con formularios «muertos»."""

import re
from pathlib import Path

from ..conftest import login

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "app" / "static"


def test_static_urls_are_versioned_so_phones_never_keep_old_css_or_js(client):
    html = client.get("/").get_data(as_text=True)
    assert re.search(r"/static/css/app\.css\?v=\d+", html)
    assert re.search(r"/static/js/app\.js\?v=\d+", html)
    assert not re.search(r"/static/uploads/[^\"' ]*\?v=", html)  # las fotos subidas no cambian nunca: sin versión


def test_version_changes_with_the_file(app, tmp_path):
    from flask import url_for

    with app.test_request_context():
        first = url_for("static", filename="css/app.css")
        assert url_for("static", filename="css/app.css") == first
        assert "?v=" in first and "?v=" not in url_for("static", filename="uploads/x.webp")
        assert "?v=" not in url_for("static", filename="no-existe.css")  # un archivo que no existe no rompe la página


def test_service_worker_does_not_pin_old_code_or_store_private_pages():
    sw = (STATIC / "sw.js").read_text(encoding="utf-8")
    assert "const VERSION = 'v2'" in sw  # subió de v1: los teléfonos descartan la caché vieja
    code_branch = sw[sw.index("(js|css|webmanifest)") : sw.index("// Fotos e iconos")]
    assert "fetch(req)" in code_branch and code_branch.index("fetch(req)") < code_branch.index(
        "caches.match"
    )  # red primero
    private = re.search(r"const PRIVATE = (/.*/);", sw).group(1)
    pattern = re.compile(private[1:-1])
    for path in ("/panel/perfil", "/ingresar", "/registro", "/recuperar/codigo", "/favoritos", "/anuncio/5/contacto",
                 "/anuncio/5/whatsapp", "/vendedor/3/contacto", "/publicar", "/admin/usuarios"):  # fmt: skip
        assert pattern.search(path), path
    for path in ("/", "/anuncios", "/agricolas/cafe/cafe-pergamino-seco-3-14", "/vendedor/3", "/precios"):
        assert not pattern.search(path), path
    assert "no-store" in sw  # tampoco se guarda lo que el servidor pide no guardar


def test_publish_wizard_degrades_gracefully_when_its_script_does_not_run(seller):
    html = seller.get("/publicar").get_data(as_text=True)
    assert 'id="wizard-fallback"' in html and 'id="wizard-reload"' in html and "<noscript>" in html
    assert "publish.js" in html
    script = (STATIC / "js" / "publish.js").read_text(encoding="utf-8")
    assert script.index("data-wizard") < script.index(
        "showStep(step);\n})();"
    )  # se marca justo antes de mostrar el paso
    css = (STATIC / "css" / "app.css").read_text(encoding="utf-8")
    assert "#pub-form[data-wizard] .step-hidden" in css  # los pasos solo se ocultan si el asistente arrancó
    assert not re.search(r"(^|[},])\.step-hidden[,{]", css)  # ninguna regla oculta los pasos sin pasar por data-wizard
    assert "#pub-form:not([data-wizard]) #btn-submit" in css  # y sin el asistente, el botón Publicar sí se ve


def test_info_alerts_with_inline_text_are_wrapped_so_they_do_not_split_into_columns(client):
    """`.alert` es una fila flex: el texto suelto y las <strong> se partirían en columnas si no van envueltos."""
    for path in ("/registro", "/recuperar"):
        html = client.get(path).get_data(as_text=True)
        for alert in re.findall(r'<p class="alert[^"]*"[^>]*>(.*?)</p>', html, re.S):
            assert alert.lstrip().startswith(("<span", "<div", "<svg")), (path, alert[:60])
    login(client, "3101112233")
    html = client.get("/anuncios/mapa").get_data(as_text=True)
    assert '<noscript><p class="alert alert-info mt-3"><span>' in html

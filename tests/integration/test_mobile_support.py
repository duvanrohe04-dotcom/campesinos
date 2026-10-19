"""Compatibilidad con celulares: permisos del navegador y piezas que usan los scripts del teléfono."""

from app.constants import PERMISSIONS_POLICY


def test_microphone_is_allowed_so_voice_dictation_can_work(client):
    policy = client.get("/").headers["Permissions-Policy"]
    assert policy == PERMISSIONS_POLICY
    assert "microphone=(self)" in policy and "microphone=()" not in policy
    assert "geolocation=(self)" in policy and "camera=(self)" in policy


def test_bottom_nav_can_be_hidden_while_typing(client):
    assert "data-bottom-nav" in client.get("/").get_data(as_text=True)
    css = client.get("/static/css/app.css").get_data(as_text=True)
    assert ".kb-open [data-bottom-nav]" in css


def test_village_list_script_rebuilds_the_options(client):
    script = client.get("/static/js/app.js").get_data(as_text=True)
    assert "_allOptions" in script and "o.hidden" not in script  # ya no depende de ocultar opciones


def test_publish_script_has_fallbacks_for_old_phones(client):
    script = client.get("/static/js/publish.js").get_data(as_text=True)
    assert "canTransfer" in script  # sin DataTransfer las fotos se envían igual
    assert "COMPRESS_TIMEOUT_MS" in script  # la compresión nunca se queda esperando
    assert "image/jpeg" in script  # navegadores sin WebP no suben PNG pesados
    assert "if (step < 4) { e.preventDefault()" in script  # tecla «Ir» del teclado: avanza, no publica a medias


def test_geolocation_has_a_timeout(client):
    script = client.get("/static/js/map.js").get_data(as_text=True)
    assert "timeout: 15000" in script and script.count("GEO_OPTIONS") >= 3


def test_hidden_attribute_always_hides_even_on_flex_components(client):
    """Sin esto, `.alert` (display: flex) anulaba `hidden` y el aviso «El formulario no terminó de cargar» se veía siempre."""
    css = client.get("/static/css/app.css").get_data(as_text=True)
    assert "[hidden]{display:none!important}" in css


def test_voice_buttons_are_shown_when_the_browser_supports_them(client):
    """Los botones «Escuchar» y «Hablar» vienen ocultos en el HTML: el script debe mostrarlos si hay soporte."""
    script = client.get("/static/js/a11y.js").get_data(as_text=True)
    assert "b.hidden = !canSpeak" in script and "b.hidden = !Recognition" in script

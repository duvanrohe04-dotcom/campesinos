"""Revisión automática de accesibilidad básica sobre las páginas públicas y el asistente de publicar."""

from html.parser import HTMLParser

import pytest

from app.models import Listing

from ..conftest import login, url_of

INPUT_TYPES_WITHOUT_LABEL = {"hidden", "submit", "button"}


class A11yChecker(HTMLParser):
    """Reúne problemas típicos: imágenes sin alt, controles sin etiqueta, botones sin texto, varios h1, sin lang."""

    def __init__(self):
        super().__init__()
        self.problems: list[str] = []
        self.labels_for: set[str] = set()
        self.controls: list[dict] = []
        self.h1 = 0
        self.lang = None
        self.in_label = 0
        self.button_stack: list[dict] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "img" and "alt" not in a:
            self.problems.append(f"img sin alt: {a.get('src')}")
        if tag == "label":
            self.in_label += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        if a.get("id"):
            self.ids.add(a["id"])
        if tag in ("input", "select", "textarea"):
            if a.get("type") in INPUT_TYPES_WITHOUT_LABEL or a.get("disabled") is not None and tag == "input":
                return
            self.controls.append({**a, "tag": tag, "inside_label": bool(self.in_label)})
        if tag in ("button", "a"):
            self.button_stack.append({"tag": tag, "attrs": a, "text": ""})

    def handle_endtag(self, tag):
        if tag == "label":
            self.in_label -= 1
        if tag in ("button", "a") and self.button_stack:
            item = self.button_stack.pop()
            a = item["attrs"]
            if tag == "a" and not a.get("href"):
                return
            has_name = item["text"].strip() or a.get("aria-label") or a.get("title")
            if not has_name and "sr-only" not in (a.get("class") or ""):
                self.problems.append(f"{tag} sin texto accesible: {a}")

    def handle_data(self, data):
        for item in self.button_stack:
            item["text"] += data

    def finish(self):
        for c in self.controls:
            labelled = (
                c.get("id") in self.labels_for or c["inside_label"] or c.get("aria-label") or c.get("aria-labelledby")
            )
            if not labelled and c.get("class", "").find("sr-only") < 0 and "opacity-0" not in c.get("class", ""):
                self.problems.append(f"control sin etiqueta: {c['tag']} name={c.get('name')}")
        if self.lang != "es-CO":
            self.problems.append(f"lang={self.lang}")
        if self.h1 != 1:
            self.problems.append(f"h1 = {self.h1}")
        return self.problems


def check(client, path):
    response = client.get(path)
    assert response.status_code == 200, path
    checker = A11yChecker()
    checker.feed(response.get_data(as_text=True))
    return checker.finish()


PUBLIC_PAGES = [
    "/", "/anuncios", "/anuncios?cat=bovinos", "/como-funciona", "/preguntas-frecuentes", "/contacto",
    "/quienes-somos", "/terminos", "/privacidad", "/consejos-compra-segura", "/ingresar", "/registro",
]  # fmt: skip


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_pages_have_basic_accessibility(client, path):
    assert check(client, path) == []


def test_detail_profile_and_forms_are_accessible(client):
    listing = Listing.query.filter(Listing.title.contains("Novillo cebú")).first()
    assert check(client, url_of(listing)) == []
    assert check(client, f"/vendedor/{listing.user_id}") == []
    assert check(client, f"/anuncio/{listing.id}/reportar") == []


def test_publish_wizard_and_panel_are_accessible(client):
    from app.extensions import db
    from app.models import User

    User.by_phone("3123334455").email = "luis@example.com"  # con correo sin verificar: abre la pantalla de verificación
    db.session.commit()
    login(client, "3123334455")
    for path in ("/publicar", "/panel", "/panel/perfil", "/notificaciones", "/verificar-correo"):
        assert check(client, path) == [], path


def test_skip_link_text_size_and_voice_controls_exist(client):
    html = client.get("/").get_data(as_text=True)
    assert "Saltar al contenido" in html and 'id="contenido"' in html
    assert "data-text-size" in html and "js/a11y.js" in html
    login(client, "3101112233")
    form = client.get("/publicar").get_data(as_text=True)
    assert (
        form.count("data-speak=") >= 4 and 'data-dictate="f-title"' in form and 'data-dictate="f-description"' in form
    )
    listing = Listing.query.filter(Listing.title.contains("Novillo cebú")).first()
    assert "Escuchar este anuncio" in client.get(url_of(listing)).get_data(as_text=True)


def test_form_errors_use_plain_spanish(client):
    data = {"role": "otro", "municipality_id": "999", "accept_terms": "y", "name": "Ana", "phone": "3150000000",
            "password": "secreto1"}  # fmt: skip
    html = client.post("/registro", data=data).get_data(as_text=True)
    for technical in ("Not a valid", "This field", "Invalid value", "CSRF", "Traceback"):
        assert technical not in html
    assert "Elige tu municipio" in html

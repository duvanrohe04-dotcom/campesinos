"""Botón «Volver»: sale en todas las páginas menos el inicio y lleva a un destino sensato si no hay historial."""

import re

import pytest

from app.models import AttributeDef, Category, Listing

from ..conftest import url_of


def back_href(response) -> str | None:
    match = re.search(r'<a href="([^"]*)" data-back', response.get_data(as_text=True))
    return match.group(1) if match else None


def test_home_has_no_back_button(client):
    assert back_href(client.get("/")) is None


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/anuncios", "/"),
        ("/anuncios/mapa", "/anuncios"),
        ("/precios", "/"),
        ("/agenda", "/"),
        ("/consejos", "/"),
        ("/precios/vacas", None),  # 404: el botón existe y lleva al inicio o a precios
        ("/contacto", "/"),
        ("/terminos", "/"),
        ("/ingresar", "/"),
        ("/registro", "/"),
        ("/recuperar", "/"),
        ("/no-existe-esta-pagina/x", "/"),
    ],
)
def test_public_pages_have_a_back_button(client, path, expected):
    href = back_href(client.get(path))
    assert href is not None, path
    if expected:
        assert href == expected, path


def test_listing_detail_goes_back_to_the_list(client):
    listing = Listing.query.first()
    assert back_href(client.get(url_of(listing))) == "/anuncios"


def test_panel_pages_go_back_to_the_panel_or_profile(seller):
    assert back_href(seller.get("/panel")) == "/"
    assert back_href(seller.get("/panel/perfil")) == "/panel"
    assert back_href(seller.get("/favoritos")) == "/anuncios"
    assert back_href(seller.get("/notificaciones")) == "/panel"
    assert back_href(seller.get("/publicar")) == "/panel"
    assert back_href(seller.get("/panel/contrasena")) == "/panel/perfil"
    assert back_href(seller.get("/panel/cuenta")) == "/panel/perfil"


def test_each_page_shows_only_one_back_button(seller):
    for path in ("/panel/contrasena", "/panel/cuenta", "/anuncios", "/panel/perfil"):
        assert seller.get(path).get_data(as_text=True).count("data-back") == 1, path


def test_contact_page_goes_back_to_the_listing(client):
    listing = Listing.query.filter_by(status="active").first()
    response = client.get(f"/anuncio/{listing.id}/contacto")
    assert back_href(response) == url_of(listing)
    assert "Volver al anuncio" in response.get_data(as_text=True)


def test_admin_pages_go_back_to_the_right_place(admin):
    assert back_href(admin.get("/admin/")) == "/"
    for path in ("/admin/usuarios", "/admin/anuncios", "/admin/reportes", "/admin/categorias", "/admin/eventos"):
        assert back_href(admin.get(path)) == "/admin/", path
    assert back_href(admin.get("/admin/eventos/nuevo")) == "/admin/eventos"
    assert back_href(admin.get("/admin/articulos/nuevo")) == "/admin/articulos"
    category = Category.root_by_slug("bovinos")
    assert back_href(admin.get(f"/admin/categorias/{category.id}/atributos")) == "/admin/categorias"
    assert back_href(admin.get(f"/admin/categorias/{category.id}/atributos/nuevo")).endswith("/atributos")
    attr = AttributeDef.query.filter_by(category_id=category.id).first()
    assert back_href(admin.get(f"/admin/atributos/{attr.id}/editar")).endswith("/atributos")
    assert back_href(admin.get("/admin/municipios/1")) == "/admin/municipios"


def test_back_button_script_is_served(client):
    script = client.get("/static/js/app.js").get_data(as_text=True)
    assert "[data-back]" in script and "history.back()" in script

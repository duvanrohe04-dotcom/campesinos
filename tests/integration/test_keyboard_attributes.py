"""Regresión: un campo con `inputmode="None"` (WTForms escribe None como texto) deja al celular sin teclado."""

import re

import pytest

from app.models import AttributeDef, Category, Listing, User

from ..conftest import login, url_of

BAD_VALUE = re.compile(r'="None"|=None\b')  # «None» de Python con mayúscula; `fill="none"` de los iconos SVG es válido
KEYBOARD_OFF = re.compile(r'inputmode="none"', re.IGNORECASE)

PUBLIC_PATHS = [
    "/", "/registro", "/ingresar", "/recuperar", "/contacto", "/anuncios", "/anuncios/mapa", "/precios",
    "/agenda", "/consejos", "/como-funciona", "/preguntas-frecuentes", "/terminos", "/privacidad",
]  # fmt: skip
USER_PATHS = [
    "/panel", "/panel/perfil", "/panel/contrasena", "/panel/cuenta", "/publicar", "/favoritos",
    "/notificaciones", "/busquedas-guardadas",
]  # fmt: skip


def assert_keyboard_friendly(response, path):
    assert response.status_code == 200, path
    html = response.get_data(as_text=True)
    assert not KEYBOARD_OFF.search(html), f"{path}: un campo apaga el teclado del celular (inputmode=none)"
    assert not BAD_VALUE.search(html), f"{path}: hay un atributo con el texto None"


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_never_switch_the_keyboard_off(client, path):
    assert_keyboard_friendly(client.get(path), path)


@pytest.mark.parametrize("path", USER_PATHS)
def test_user_pages_never_switch_the_keyboard_off(seller, path):
    assert_keyboard_friendly(seller.get(path), path)


def test_recovery_code_page_and_listing_pages(client):
    client.post("/recuperar", data={"phone": "3101112233"})
    assert_keyboard_friendly(client.get("/recuperar/codigo"), "/recuperar/codigo")
    listing = Listing.query.first()
    assert_keyboard_friendly(client.get(url_of(listing)), "detalle del anuncio")
    seller = User.by_phone("3101112233")
    assert_keyboard_friendly(client.get(f"/vendedor/{seller.id}"), "perfil público")
    assert_keyboard_friendly(client.get(f"/anuncio/{listing.id}/reportar"), "reportar")


def test_admin_pages_never_switch_the_keyboard_off(client):
    login(client, "3000000000", "admin12345")
    category = Category.root_by_slug("bovinos")
    attr = AttributeDef.query.filter_by(category_id=category.id).first()
    for path in (
        "/admin/", "/admin/usuarios", "/admin/anuncios", "/admin/categorias", f"/admin/categorias/{category.id}/editar",
        f"/admin/categorias/{category.id}/atributos/nuevo", f"/admin/atributos/{attr.id}/editar", "/admin/municipios",
        "/admin/eventos/nuevo", "/admin/articulos/nuevo",
    ):  # fmt: skip
        assert_keyboard_friendly(client.get(path), path)


def test_login_fields_only_carry_the_attributes_they_need(client):
    html = client.get("/ingresar").get_data(as_text=True)
    password = re.search(r'<input[^>]*id="password"[^>]*>', html).group(0)
    assert "inputmode" not in password and 'autocomplete="current-password"' in password
    phone = re.search(r'<input[^>]*id="phone"[^>]*>', html).group(0)
    assert 'inputmode="numeric"' in phone  # el celular sí abre el teclado numérico

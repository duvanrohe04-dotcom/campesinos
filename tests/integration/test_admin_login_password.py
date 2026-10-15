"""Admin que entra con un usuario escrito («admin») y cambio de contraseña desde el panel."""

import pytest

from app.config import TestingConfig
from app.extensions import db
from app.models import User
from app.services.seeding import seed_admin

from ..conftest import login


@pytest.fixture()
def named_admin(app):
    """Administrador con usuario «admin» y clave admin123, creado como lo hace el seed con ADMIN_PHONE=Admin."""
    app.config.update(ADMIN_PHONE="Admin", ADMIN_PASSWORD="admin123")
    assert seed_admin() is True
    return User.by_phone("admin")


def test_admin_enters_with_username_in_any_case(client, named_admin):
    for typed in ("admin", "  Admin ", "ADMIN"):
        response = login(client, typed, "admin123")
        assert response.status_code == 302, typed
        assert client.get("/admin/").status_code == 200
        client.post("/salir")


def test_wrong_password_for_named_admin_is_rejected(client, named_admin):
    assert login(client, "admin", "otra-clave").status_code == 200
    assert client.get("/admin/").status_code == 302


def test_regular_users_cannot_log_in_with_a_word(client, seller):
    user = User.by_phone("3101112233")
    user.phone = "pedro"  # aunque tuviera un valor así guardado, solo un administrador puede usarlo
    db.session.commit()
    client.post("/salir")
    assert login(client, "pedro").status_code == 200
    assert client.get("/panel").status_code == 302


def test_seed_admin_refuses_a_username_longer_than_the_column(app):
    app.config.update(ADMIN_PHONE="administrador-general", ADMIN_PASSWORD="admin123")
    assert seed_admin() is False
    assert User.by_phone("administrador-general") is None


def test_user_changes_password_from_the_panel(seller, client):
    page = seller.get("/panel/contrasena")
    assert page.status_code == 200 and "Cambiar mi contraseña" in page.get_data(as_text=True)
    data = {"current_password": "campo123", "password": "nueva-clave-1", "confirm": "nueva-clave-1"}
    assert seller.post("/panel/contrasena", data=data).status_code == 302
    seller.post("/salir")
    assert login(client, "3101112233", "campo123").status_code == 200  # la vieja ya no sirve
    assert login(client, "3101112233", "nueva-clave-1").status_code == 302


@pytest.mark.parametrize(
    ("current", "new", "confirm", "message"),
    [
        ("incorrecta", "nueva-clave-1", "nueva-clave-1", "Esa no es tu contraseña actual."),
        ("campo123", "nueva-clave-1", "distinta-clave", "Las contraseñas no son iguales."),
        ("campo123", "123", "123", "Mínimo"),
    ],
)
def test_change_password_validations(seller, current, new, confirm, message):
    data = {"current_password": current, "password": new, "confirm": confirm}
    response = seller.post("/panel/contrasena", data=data)
    assert response.status_code == 200 and message in response.get_data(as_text=True)
    assert User.by_phone("3101112233").check_password("campo123")


def test_change_password_requires_login(client):
    assert client.get("/panel/contrasena").status_code == 302
    assert client.post("/panel/contrasena", data={"password": "x"}).status_code == 302


def test_named_admin_can_change_the_default_password(client, named_admin):
    login(client, "admin", "admin123")
    data = {"current_password": "admin123", "password": "clave-larga-segura", "confirm": "clave-larga-segura"}
    assert client.post("/panel/contrasena", data=data).status_code == 302
    client.post("/salir")
    assert login(client, "admin", "admin123").status_code == 200
    assert login(client, "admin", "clave-larga-segura").status_code == 302


def test_testing_config_still_uses_the_phone_admin():
    assert TestingConfig.ADMIN_PHONE == "3000000000"

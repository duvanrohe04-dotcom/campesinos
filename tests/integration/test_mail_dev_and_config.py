"""Correo en desarrollo (el código se ve en pantalla) y aviso cuando el correo no está bien configurado."""

import re

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User
from app.services import mailer
from app.services.seeding import seed_all

from ..conftest import login


def _app(tmp_path, **settings):
    config = type("Config", (TestingConfig,), {"UPLOAD_FOLDER": str(tmp_path), **settings})
    return create_app(config)


@pytest.fixture()
def dev_client(tmp_path):
    app = _app(tmp_path, MAIL_BACKEND="console", DEBUG=True)
    with app.app_context():
        db.create_all()
        seed_all(samples=True)
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_debug_console_mode_shows_the_recovery_code_on_screen(dev_client):
    assert User.by_phone("3101112233").email_verified  # el de ejemplo con correo verificado
    response = dev_client.post("/recuperar", data={"phone": "3101112233"}, follow_redirects=True)
    text = response.get_data(as_text=True)
    assert "Modo desarrollo" in text
    code = re.search(r"Tu código es (\d{6})", text).group(1)
    data = {"code": code, "password": "clave-nueva-1"}
    assert dev_client.post("/recuperar/codigo", data=data).status_code == 302
    assert login(dev_client, "3101112233", "clave-nueva-1").status_code == 302


def test_account_without_verified_email_gets_no_code_but_no_hint_of_it(dev_client):
    user = User.by_phone("3112223344")
    assert not user.email_verified
    response = dev_client.post("/recuperar", data={"phone": "3112223344"}, follow_redirects=True)
    assert "Modo desarrollo" not in response.get_data(as_text=True)  # no revela quién tiene cuenta


def test_verification_code_is_also_shown_in_development(dev_client):
    login(dev_client, "3112223344")
    user = User.by_phone("3112223344")
    user.email = "marta@example.com"
    db.session.commit()
    response = dev_client.post("/verificar-correo/enviar", follow_redirects=True)
    assert re.search(r"Tu código es \d{6}", response.get_data(as_text=True))


def test_code_is_not_shown_outside_debug(client):  # configuración de pruebas: correo en memoria, sin DEBUG
    client.post("/recuperar", data={"phone": "3101112233"}, follow_redirects=True)
    assert mailer.outbox and "Modo desarrollo" not in client.get("/").get_data(as_text=True)


def test_startup_warns_when_production_would_not_send_mail(tmp_path, caplog):
    with caplog.at_level("WARNING"):
        _app(tmp_path, MAIL_BACKEND="console", DEBUG=False, TESTING=False)
    assert "NO se envían" in caplog.text


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({"MAIL_BACKEND": "smtp", "MAIL_SERVER": ""}, "falta MAIL_SERVER"),
        (
            {"MAIL_BACKEND": "smtp", "MAIL_SERVER": "smtp.x.com", "MAIL_USERNAME": "", "MAIL_PASSWORD": ""},
            "MAIL_USERNAME",
        ),
        ({"MAIL_BACKEND": "console", "DEBUG": False, "TESTING": False}, "NO se envían"),
        ({"MAIL_BACKEND": "console", "DEBUG": True, "TESTING": False}, None),
        ({"MAIL_BACKEND": "memory"}, None),
        ({"MAIL_BACKEND": "smtp", "MAIL_SERVER": "s", "MAIL_USERNAME": "u", "MAIL_PASSWORD": "p"}, None),
    ],
)
def test_config_problem(settings, expected):
    base = {"MAIL_SERVER": "", "MAIL_USERNAME": "", "MAIL_PASSWORD": "", "DEBUG": False, "TESTING": False}
    problem = mailer.config_problem({**base, **settings})
    assert (expected in problem) if expected else problem is None

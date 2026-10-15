"""La sesión no se pierde porque el celular cambie de red (Wi-Fi ↔ datos móviles) ni de IP.

Estas pruebas NO usan la fixture `app` a propósito: esa deja un contexto abierto durante toda la prueba y Flask-Login
guarda al usuario en él, así que la protección de sesión ni se evaluaría. Aquí cada petición es independiente, como en la vida real.
"""

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.services.seeding import seed_all

WIFI = {"REMOTE_ADDR": "192.168.1.20"}
DATOS_MOVILES = {"REMOTE_ADDR": "190.85.44.7"}


@pytest.fixture()
def real_client(tmp_path):
    class Config(TestingConfig):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(tmp_path / "campo.db").replace("\\", "/")
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        seed_all(samples=False)
        db.session.remove()
    yield app.test_client()  # ya sin contexto abierto
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def sign_in(client, remember=False, **environ):
    data = {"phone": "3000000000", "password": "admin12345"}
    if remember:
        data["remember"] = "y"
    return client.post("/ingresar", data=data, environ_overrides=environ)


def test_changing_ip_does_not_log_the_user_out(real_client):
    assert sign_in(real_client, **WIFI).status_code == 302
    assert real_client.get("/panel", environ_overrides=WIFI).status_code == 200
    # el teléfono pasa a datos móviles: otra IP en la siguiente petición
    assert real_client.get("/panel", environ_overrides=DATOS_MOVILES).status_code == 200
    assert real_client.get("/publicar", environ_overrides=DATOS_MOVILES).status_code == 200


def test_changing_browser_string_does_not_log_the_user_out(real_client):
    sign_in(real_client)
    assert real_client.get("/panel", headers={"User-Agent": "Mozilla/5.0 Android 11 Chrome/120"}).status_code == 200
    assert real_client.get("/panel", headers={"User-Agent": "Mozilla/5.0 Android 11 Chrome/121"}).status_code == 200


def test_remember_me_survives_a_network_change(real_client):
    response = sign_in(real_client, remember=True, **WIFI)
    assert "campo_directo_remember" in "".join(response.headers.getlist("Set-Cookie"))
    # se pierde la cookie de sesión pero queda la de «recordarme», y la IP es otra
    real_client.delete_cookie("campo_directo_session")
    assert real_client.get("/panel", environ_overrides=DATOS_MOVILES).status_code == 200


def test_a_logged_out_visitor_is_still_sent_to_login(real_client):
    assert real_client.get("/panel").status_code == 302

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User

from ..conftest import login

REGISTER = {"role": "seller", "name": "Ana Ruiz", "phone": "3159998877", "password": "secreto1",
            "municipality_id": 1, "accept_terms": "y"}  # fmt: skip


def test_register_and_login(client):
    response = client.post("/registro", data=REGISTER, follow_redirects=False)
    assert response.status_code == 302
    assert User.by_phone("3159998877").role == "seller"


def test_register_rejects_bad_and_duplicate_phone(client):
    html = client.post("/registro", data={**REGISTER, "phone": "12345"}).get_data(as_text=True)
    assert "celular de 10 números" in html
    html = client.post("/registro", data={**REGISTER, "phone": "3101112233"}).get_data(as_text=True)
    assert "ya tiene cuenta" in html


def test_register_requires_terms_and_records_acceptance(client):
    data = {k: v for k, v in REGISTER.items() if k != "accept_terms"}
    response = client.post("/registro", data=data)
    assert response.status_code == 200 and "aceptar los términos" in response.get_data(as_text=True)
    assert User.by_phone("3159998877") is None
    client.post("/registro", data=REGISTER)
    user = User.by_phone("3159998877")
    assert user.terms_accepted_at is not None and user.terms_version


def test_login_wrong_password_then_lockout(client):
    for _ in range(5):
        login(client, "3101112233", "mala")
    assert User.by_phone("3101112233").is_locked()
    response = login(client, "3101112233", "campo123")  # correcta, pero bloqueada
    assert response.status_code == 200 and "Demasiados intentos" in response.get_data(as_text=True)


def test_login_ok_and_open_redirect_blocked(client):
    response = client.post("/ingresar?next=//evil.com", data={"phone": "3101112233", "password": "campo123"})
    assert response.status_code == 302 and "evil.com" not in response.headers["Location"]


def test_logout_requires_post(seller):
    assert seller.get("/salir").status_code == 405
    assert seller.post("/salir").status_code == 302


def test_login_is_rate_limited_per_ip(tmp_path):
    class Config(TestingConfig):
        RATELIMIT_ENABLED = True
        LOGIN_RATE_LIMIT = "3 per minute"
        UPLOAD_FOLDER = str(tmp_path)

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        client = app.test_client()
        codes = [client.post("/ingresar", data={"phone": "3000000001", "password": "x"}).status_code
                 for _ in range(5)]  # fmt: skip
        assert codes[:3] == [200, 200, 200] and 429 in codes[3:]
        db.drop_all()

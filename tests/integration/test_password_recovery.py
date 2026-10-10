"""Correo en la cuenta: registro, cambio de correo, recuperar contraseña y enviador SMTP."""

import re
from datetime import timedelta

from app.extensions import db
from app.models import User
from app.services import mailer
from app.utils import utcnow

from ..conftest import login
from .test_auth import REGISTER

PHONE = "3112223344"


def code_in(mail):
    return re.search(r"\b(\d{6})\b", mail.body).group(1)


def verified_user(email="marta@example.com"):
    user = User.by_phone(PHONE)
    user.email, user.email_verified_at = email, utcnow()
    db.session.commit()
    return user


def test_register_with_email_sends_code_and_goes_to_verify(client):
    mailer.outbox.clear()
    response = client.post("/registro", data={**REGISTER, "email": "  Ana@Example.COM "})
    assert response.status_code == 302 and response.headers["Location"].endswith("/verificar-correo")
    user = User.by_phone("3159998877")
    assert user.email == "ana@example.com" and not user.email_verified
    assert mailer.outbox[-1].to == "ana@example.com"
    client.post("/verificar-correo", data={"code": code_in(mailer.outbox[-1])})
    assert db.session.get(User, user.id).email_verified


def test_register_without_email_still_works(client):
    response = client.post("/registro", data=REGISTER)
    assert response.status_code == 302 and response.headers["Location"].endswith("/")
    assert User.by_phone("3159998877").email is None


def test_register_rejects_bad_and_duplicate_email(client):
    verified_user("marta@example.com")
    html = client.post("/registro", data={**REGISTER, "email": "no-es-correo"}).get_data(as_text=True)
    assert "correo válido" in html
    html = client.post("/registro", data={**REGISTER, "email": "MARTA@example.com"}).get_data(as_text=True)
    assert "ya está en otra cuenta" in html
    assert User.by_phone("3159998877") is None


def test_changing_email_requires_new_verification(seller):
    mailer.outbox.clear()
    user = verified_user("viejo@example.com")
    seller.post("/salir")
    login(seller, PHONE)
    data = {"name": "Marta", "municipality_id": user.municipality_id, "email": "nuevo@example.com"}
    response = seller.post("/panel/perfil", data=data)
    assert response.status_code == 302 and response.headers["Location"].endswith("/verificar-correo")
    db.session.refresh(user)
    assert user.email == "nuevo@example.com" and not user.email_verified
    assert mailer.outbox[-1].to == "nuevo@example.com"


def test_password_recovery_end_to_end(client):
    mailer.outbox.clear()
    verified_user()
    sent = client.post("/recuperar", data={"phone": PHONE})
    assert sent.status_code == 302 and sent.headers["Location"].endswith("/recuperar/codigo")
    assert len(mailer.outbox) == 1 and mailer.outbox[0].to == "marta@example.com"

    bad = client.post("/recuperar/codigo", data={"code": "000000", "password": "nueva-clave"})
    assert "no es correcto" in bad.get_data(as_text=True) or "venció" in bad.get_data(as_text=True)
    done = client.post("/recuperar/codigo", data={"code": code_in(mailer.outbox[0]), "password": "nueva-clave"})
    assert done.status_code == 302 and done.headers["Location"].endswith("/ingresar")

    assert login(client, PHONE, "nueva-clave").status_code == 302
    assert "Mi panel" in client.get("/panel").get_data(as_text=True)


def test_old_password_stops_working_after_reset(client):
    mailer.outbox.clear()
    verified_user()
    client.post("/recuperar", data={"phone": PHONE})
    client.post("/recuperar/codigo", data={"code": code_in(mailer.outbox[0]), "password": "nueva-clave"})
    old = client.post("/ingresar", data={"phone": PHONE, "password": "campo123"})
    assert old.status_code == 200 and "incorrectos" in old.get_data(as_text=True)


def test_recovery_does_not_reveal_whether_phone_exists(client):
    mailer.outbox.clear()
    verified_user()
    known = client.post("/recuperar", data={"phone": PHONE})
    unknown = client.post("/recuperar", data={"phone": "3199999999"})
    nonsense = client.post("/recuperar", data={"phone": "abc"})
    assert known.status_code == unknown.status_code == nonsense.status_code == 302
    assert known.headers["Location"] == unknown.headers["Location"] == nonsense.headers["Location"]
    assert len(mailer.outbox) == 1  # solo el celular real con correo verificado recibe algo
    page = client.get("/recuperar/codigo").get_data(as_text=True)
    assert "correo verificado" in page


def test_recovery_needs_verified_email(client):
    mailer.outbox.clear()
    user = User.by_phone(PHONE)
    user.email = "sin-verificar@example.com"
    db.session.commit()
    client.post("/recuperar", data={"phone": PHONE})
    assert mailer.outbox == []
    done = client.post("/recuperar/codigo", data={"code": "123456", "password": "nueva-clave"})
    assert "venció o no es correcto" in done.get_data(as_text=True)


def test_reset_code_cannot_be_reused_or_brute_forced(client):
    mailer.outbox.clear()
    verified_user()
    client.post("/recuperar", data={"phone": PHONE})
    real = code_in(mailer.outbox[0])
    wrong = "999999" if real != "999999" else "888888"
    for _ in range(5):
        client.post("/recuperar/codigo", data={"code": wrong, "password": "nueva-clave"})
    blocked = client.post("/recuperar/codigo", data={"code": real, "password": "nueva-clave"})
    assert "Demasiados intentos" in blocked.get_data(as_text=True)
    assert User.by_phone(PHONE).check_password("campo123")


def test_short_new_password_keeps_the_code_valid(client):
    mailer.outbox.clear()
    verified_user()
    client.post("/recuperar", data={"phone": PHONE})
    code = code_in(mailer.outbox[0])
    assert "Mínimo" in client.post("/recuperar/codigo", data={"code": code, "password": "123"}).get_data(as_text=True)
    ok = client.post("/recuperar/codigo", data={"code": code, "password": "clave-larga"})
    assert ok.status_code == 302 and ok.headers["Location"].endswith("/ingresar")


def test_reset_code_page_requires_the_first_step(client):
    assert client.get("/recuperar/codigo").headers["Location"].endswith("/recuperar")


def test_reset_clears_login_lockout(client):
    mailer.outbox.clear()
    user = verified_user()
    user.locked_until = utcnow() + timedelta(minutes=30)
    db.session.commit()
    client.post("/recuperar", data={"phone": PHONE})
    client.post("/recuperar/codigo", data={"code": code_in(mailer.outbox[0]), "password": "nueva-clave"})
    assert login(client, PHONE, "nueva-clave").status_code == 302


def test_suspended_account_gets_a_clear_message(client):
    user = User.by_phone(PHONE)
    user.is_enabled = False
    db.session.commit()
    html = client.post("/ingresar", data={"phone": PHONE, "password": "campo123"}).get_data(as_text=True)
    assert "cuenta está suspendida" in html
    html = client.post("/ingresar", data={"phone": PHONE, "password": "mala"}).get_data(as_text=True)
    assert "incorrectos" in html  # sin la clave correcta no se revela el estado de la cuenta


def test_old_verification_url_redirects(seller):
    assert seller.get("/verificar-celular").headers["Location"].endswith("/verificar-correo")


# ---------- Enviador de correo ----------
def test_smtp_backend_logs_in_and_sends_over_tls(app, monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context=None):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user))

        def send_message(self, message):
            calls.append(("send", message["To"], message["Subject"]))

    monkeypatch.setattr("app.services.mailer.smtplib.SMTP", FakeSMTP)
    app.config.update(MAIL_BACKEND="smtp", MAIL_SERVER="smtp.example.com", MAIL_USERNAME="user", MAIL_PASSWORD="pw")
    mailer.send_email("a@example.com", "Asunto", "Cuerpo")
    assert calls == [
        ("connect", "smtp.example.com", 587),
        ("starttls",),
        ("login", "user"),
        ("send", "a@example.com", "Asunto"),
    ]


def test_smtp_failure_becomes_mail_error(app, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise OSError("conexión rechazada")

    monkeypatch.setattr("app.services.mailer.smtplib.SMTP", refuse)
    app.config.update(MAIL_BACKEND="smtp", MAIL_SERVER="smtp.example.com")
    try:
        mailer.send_email("a@example.com", "Asunto", "Cuerpo")
    except mailer.MailError as error:
        assert "conexión rechazada" in str(error)
    else:
        raise AssertionError("debía fallar")


def test_console_backend_never_prints_the_code_in_production(app, caplog):
    app.config["MAIL_BACKEND"] = "console"
    app.testing = False
    app.debug = False
    mailer.send_email("a@example.com", "Código", "Tu código es 482915")
    assert "482915" not in caplog.text and "NO se envió" in caplog.text

"""Correo de verdad: la app habla SMTP por la red con un servidor real (local), sin buzón en memoria ni sustitutos.

El servidor de abajo implementa el protocolo SMTP por sockets TCP. Así se ejecuta el código real de envío
(`smtplib`, conexión, saludo, DATA, errores de red) y se comprueba el correo que de verdad llegó al servidor."""

import email
import re
import socket
import socketserver
import threading
from email import policy

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User
from app.services import mailer
from app.services.seeding import seed_all

from ..conftest import login


class _SmtpHandler(socketserver.StreamRequestHandler):
    """Un servidor SMTP mínimo: EHLO, MAIL, RCPT, DATA, QUIT. Guarda cada correo completo recibido."""

    def reply(self, text: str) -> None:
        self.wfile.write(text.encode() + b"\r\n")
        self.wfile.flush()

    def handle(self) -> None:
        self.reply("220 localhost ESMTP prueba")
        sender, recipients = "", []
        while line := self.rfile.readline():
            command = line.decode(errors="replace").strip()
            verb = command.split(" ", 1)[0].upper()
            if verb in ("EHLO", "HELO"):
                self.reply("250 localhost")
            elif verb == "MAIL":
                sender, recipients = command.split(":", 1)[1].strip(), []
                self.reply("250 ok")
            elif verb == "RCPT":
                recipients.append(command.split(":", 1)[1].strip())
                self.reply("250 ok")
            elif verb == "DATA":
                self.reply("354 termina con un punto")
                data = b""
                while (chunk := self.rfile.readline()) and chunk != b".\r\n":
                    data += chunk
                self.server.received.append({"from": sender, "to": recipients, "raw": data})
                self.reply("250 recibido")
            elif verb == "QUIT":
                self.reply("221 adiós")
                return
            else:
                self.reply("250 ok")


class SmtpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _SmtpHandler)
        self.received: list[dict] = []

    @property
    def port(self) -> int:
        return self.server_address[1]


@pytest.fixture()
def smtp_server():
    server = SmtpServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture()
def smtp_app(tmp_path, smtp_server):
    class Config(TestingConfig):
        UPLOAD_FOLDER = str(tmp_path)
        MAIL_BACKEND = "smtp"
        MAIL_SERVER = "127.0.0.1"
        MAIL_PORT = smtp_server.port
        MAIL_USE_TLS = False
        MAIL_USERNAME = ""
        MAIL_PASSWORD = ""
        MAIL_FROM = "Campo Directo <no-responder@campodirecto.example>"
        MAIL_TIMEOUT = 5

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        seed_all(samples=True)
        yield app
        db.session.remove()
        db.drop_all()


def _parse(raw: bytes):
    return email.message_from_bytes(raw, policy=policy.default)


def test_send_email_really_reaches_an_smtp_server(smtp_app, smtp_server):
    mailer.send_email("persona@example.com", "Asunto de prueba", "Hola, esto llegó por SMTP.")
    assert len(smtp_server.received) == 1
    delivered = smtp_server.received[0]
    message = _parse(delivered["raw"])
    assert delivered["to"] == ["<persona@example.com>"]
    assert message["Subject"] == "Asunto de prueba" and "Campo Directo" in message["From"]
    assert "llegó por SMTP" in message.get_content()


def test_password_recovery_over_real_smtp_end_to_end(smtp_app, smtp_server):
    """Pide el código, lo lee del correo que recibió el servidor y cambia la clave con él: todo por la app real."""
    client = smtp_app.test_client()
    client.post("/recuperar", data={"phone": "3101112233"})
    assert len(smtp_server.received) == 1
    message = _parse(smtp_server.received[0]["raw"])
    assert smtp_server.received[0]["to"] == ["<jorge.rojas@example.com>"]
    code = re.search(r"\b(\d{6})\b", message.get_content()).group(1)

    response = client.post("/recuperar/codigo", data={"code": code, "password": "clave-nueva-77"})
    assert response.status_code == 302
    assert User.by_phone("3101112233").check_password("clave-nueva-77")
    assert login(client, "3101112233", "clave-nueva-77").status_code == 302


def test_a_wrong_code_does_not_change_the_password(smtp_app, smtp_server):
    client = smtp_app.test_client()
    client.post("/recuperar", data={"phone": "3101112233"})
    real = re.search(r"\b(\d{6})\b", _parse(smtp_server.received[0]["raw"]).get_content()).group(1)
    wrong = "000000" if real != "000000" else "111111"
    assert client.post("/recuperar/codigo", data={"code": wrong, "password": "otra-clave-1"}).status_code == 200
    assert User.by_phone("3101112233").check_password("campo123")


def test_email_verification_code_is_really_delivered(smtp_app, smtp_server):
    client = smtp_app.test_client()
    login(client, "3112223344")
    user = User.by_phone("3112223344")
    user.email = "marta@example.com"
    db.session.commit()
    client.post("/verificar-correo/enviar")
    assert [m["to"] for m in smtp_server.received] == [["<marta@example.com>"]]
    code = re.search(r"\b(\d{6})\b", _parse(smtp_server.received[0]["raw"]).get_content()).group(1)
    assert client.post("/verificar-correo", data={"code": code}).status_code == 302
    assert User.by_phone("3112223344").email_verified


def test_unreachable_server_is_reported_not_swallowed(smtp_app):
    """Un puerto cerrado de verdad: la conexión se rechaza y la app avisa sin romperse."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
    smtp_app.config["MAIL_PORT"] = closed_port
    with pytest.raises(mailer.MailError, match="SMTP"):
        mailer.send_email("persona@example.com", "x", "y")

    client = smtp_app.test_client()
    login(client, "3112223344")
    user = User.by_phone("3112223344")
    user.email = "marta@example.com"
    db.session.commit()
    response = client.post("/verificar-correo/enviar", follow_redirects=True)
    assert "No pudimos enviar el correo" in response.get_data(as_text=True)


def test_server_that_does_not_support_login_gives_a_clear_error(smtp_app):
    """Con usuario y clave configurados, un servidor sin AUTH rechaza el inicio de sesión de verdad."""
    smtp_app.config.update(MAIL_USERNAME="alguien@example.com", MAIL_PASSWORD="clave")
    with pytest.raises(mailer.MailError, match="SMTP"):
        mailer.send_email("persona@example.com", "x", "y")


def test_test_mail_command_really_sends(smtp_app, smtp_server):
    result = smtp_app.test_cli_runner().invoke(args=["test-mail", "prueba@example.com"])
    assert result.exit_code == 0 and "Listo" in result.output
    assert smtp_server.received and smtp_server.received[0]["to"] == ["<prueba@example.com>"]


def test_test_mail_command_reports_a_real_connection_failure(smtp_app):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        smtp_app.config["MAIL_PORT"] = sock.getsockname()[1]
    result = smtp_app.test_cli_runner().invoke(args=["test-mail", "prueba@example.com"])
    assert result.exit_code != 0 and "No se pudo enviar" in result.output and "MAIL_SERVER" in result.output

"""Envío de correos. El backend se elige con MAIL_BACKEND: console (desarrollo), smtp (real) o memory (pruebas)."""

import re
import smtplib
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from flask import current_app, flash, has_request_context

from ..constants import VERIFICATION_CODE_LENGTH

SMTP_SSL_PORT = 465
CODE_PATTERN = re.compile(rf"\b\d{{{VERIFICATION_CODE_LENGTH}}}\b")


class MailError(RuntimeError):
    """No se pudo enviar el correo. El mensaje es técnico: al usuario se le muestra un texto amable."""


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    body: str


# Bandeja de salida de las pruebas (MAIL_BACKEND=memory)
outbox: list[Mail] = []


def _build(mail: Mail) -> EmailMessage:
    message = EmailMessage()
    message["From"] = current_app.config["MAIL_FROM"]
    message["To"] = mail.to
    message["Subject"] = mail.subject
    message.set_content(mail.body)
    return message


def _send_smtp(mail: Mail) -> None:
    cfg = current_app.config
    if not cfg["MAIL_SERVER"]:
        raise MailError("MAIL_SERVER no está configurado.")
    try:
        if cfg["MAIL_PORT"] == SMTP_SSL_PORT:
            server = smtplib.SMTP_SSL(
                cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=cfg["MAIL_TIMEOUT"], context=ssl.create_default_context()
            )
        else:
            server = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=cfg["MAIL_TIMEOUT"])
        with server:
            if cfg["MAIL_USE_TLS"] and cfg["MAIL_PORT"] != SMTP_SSL_PORT:
                server.starttls(context=ssl.create_default_context())
            if cfg["MAIL_USERNAME"]:
                server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            server.send_message(_build(mail))
    except (OSError, smtplib.SMTPException) as error:
        raise MailError(f"Falló el envío SMTP: {error}") from error


def _show_dev_code(body: str) -> None:
    """Solo en modo desarrollo (DEBUG): muestra el código en pantalla, porque el correo no sale de verdad."""
    code = CODE_PATTERN.search(body)
    if current_app.debug and code and has_request_context():
        flash(f"Modo desarrollo: el correo no se envía. Tu código es {code.group()}.", "info")


def config_problem(config: Mapping[str, Any]) -> str | None:
    """Por qué los correos (códigos de verificación y recuperación de clave) no saldrían, o None si todo está bien."""
    backend = config["MAIL_BACKEND"]
    if backend == "smtp":
        if not config["MAIL_SERVER"]:
            return "MAIL_BACKEND=smtp pero falta MAIL_SERVER: no se enviarán códigos."
        if not (config["MAIL_USERNAME"] and config["MAIL_PASSWORD"]):
            return "Faltan MAIL_USERNAME o MAIL_PASSWORD: el servidor de correo probablemente rechazará los envíos."
    elif backend == "console" and not config.get("DEBUG") and not config.get("TESTING"):
        return "MAIL_BACKEND=console: los códigos de verificación y recuperación NO se envían. Usa MAIL_BACKEND=smtp."
    return None


def send_email(to: str, subject: str, body: str) -> None:
    """Envía un correo de texto. Lanza MailError si falla (el llamador decide qué decirle a la persona)."""
    mail = Mail(to=to, subject=subject, body=body)
    backend = current_app.config["MAIL_BACKEND"]
    if backend == "smtp":
        _send_smtp(mail)
    elif backend == "memory":
        outbox.append(mail)
    else:  # console: solo desarrollo. En producción no se imprime el contenido (lleva códigos de acceso).
        if current_app.debug or current_app.testing:
            current_app.logger.warning("[CORREO de desarrollo] Para: %s | %s\n%s", to, subject, body)
            _show_dev_code(body)
        else:
            current_app.logger.error(
                "MAIL_BACKEND=console: el correo para %s NO se envió. Configura MAIL_BACKEND=smtp.", to
            )

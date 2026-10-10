"""Códigos de un solo uso enviados por correo: verificar el correo y recuperar la contraseña."""

import hashlib
import hmac
import secrets
from datetime import timedelta

from flask import current_app

from ..constants import (
    PURPOSE_RESET_PASSWORD,
    PURPOSE_VERIFY_EMAIL,
    VERIFICATION_CODE_LENGTH,
    VERIFICATION_MAX_ATTEMPTS,
    VERIFICATION_RESEND_SECONDS,
    VERIFICATION_TTL_MINUTES,
)
from ..extensions import db
from ..models import User, VerificationCode
from ..utils import utcnow
from . import mailer

MESSAGES = {
    PURPOSE_VERIFY_EMAIL: (
        "Tu código para verificar tu correo",
        "Hola {name}, tu código para verificar tu correo en {site} es:\n\n    {code}\n\n"
        "Escríbelo en la página. Vence en {minutes} minutos.\n\n"
        "Si no fuiste tú, ignora este mensaje.",
    ),
    PURPOSE_RESET_PASSWORD: (
        "Tu código para recuperar tu contraseña",
        "Hola {name}, tu código para crear una contraseña nueva en {site} es:\n\n    {code}\n\n"
        "Escríbelo en la página junto con tu contraseña nueva. Vence en {minutes} minutos.\n\n"
        "Si no pediste este cambio, ignora este mensaje: tu contraseña sigue igual.",
    ),
}


class VerificationError(ValueError):
    """Error con mensaje en español para mostrar al usuario."""


def _hash(code: str) -> str:
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, code.encode(), hashlib.sha256).hexdigest()


def _latest(user: User, purpose: str) -> VerificationCode | None:
    return (
        VerificationCode.query.filter_by(user_id=user.id, purpose=purpose, used_at=None)
        .order_by(VerificationCode.created_at.desc(), VerificationCode.id.desc())
        .first()
    )


def seconds_until_resend(user: User, purpose: str = PURPOSE_VERIFY_EMAIL) -> int:
    last = _latest(user, purpose)
    if not last:
        return 0
    wait = VERIFICATION_RESEND_SECONDS - int((utcnow() - last.created_at).total_seconds())
    return max(wait, 0)


def _deliver(user: User, purpose: str, code: str) -> None:
    subject, template = MESSAGES[purpose]
    body = template.format(
        name=user.name.split()[0], site=current_app.config["SITE_NAME"], code=code, minutes=VERIFICATION_TTL_MINUTES
    )
    try:
        mailer.send_email(user.email, f"{subject} · {current_app.config['SITE_NAME']}", body)
    except mailer.MailError:
        current_app.logger.exception("No se pudo enviar el correo de %s al usuario %s", purpose, user.id)
        raise VerificationError("No pudimos enviar el correo ahora. Inténtalo de nuevo en unos minutos.") from None


def send_code(user: User, purpose: str = PURPOSE_VERIFY_EMAIL) -> None:
    """Genera un código nuevo (invalida los anteriores del mismo propósito) y lo envía al correo de la persona."""
    if not user.email:
        raise VerificationError("Primero agrega tu correo en tu perfil.")
    if purpose == PURPOSE_VERIFY_EMAIL and user.email_verified:
        raise VerificationError("Tu correo ya está verificado.")
    if purpose == PURPOSE_RESET_PASSWORD and not user.email_verified:
        raise VerificationError("Ese correo no está verificado.")
    wait = seconds_until_resend(user, purpose)
    if wait:
        raise VerificationError(f"Espera {wait} segundos para pedir otro código.")
    code = "".join(str(secrets.randbelow(10)) for _ in range(VERIFICATION_CODE_LENGTH))
    VerificationCode.query.filter_by(user_id=user.id, purpose=purpose, used_at=None).update({"used_at": utcnow()})
    db.session.add(
        VerificationCode(
            user_id=user.id,
            purpose=purpose,
            code_hash=_hash(code),
            expires_at=utcnow() + timedelta(minutes=VERIFICATION_TTL_MINUTES),
        )
    )
    db.session.flush()
    try:
        _deliver(user, purpose, code)
    except VerificationError:
        db.session.rollback()  # no gasta el tiempo de espera si el correo no salió
        raise
    db.session.commit()


def confirm_code(user: User, code: str, purpose: str = PURPOSE_VERIFY_EMAIL) -> None:
    """Valida el código. Lanza VerificationError con mensaje claro si falla."""
    pending = _latest(user, purpose)
    if not pending or pending.expires_at < utcnow():
        raise VerificationError("El código venció. Pide uno nuevo.")
    if pending.attempts >= VERIFICATION_MAX_ATTEMPTS:
        raise VerificationError("Demasiados intentos. Pide un código nuevo.")
    pending.attempts += 1
    if not hmac.compare_digest(pending.code_hash, _hash((code or "").strip())):
        db.session.commit()
        raise VerificationError("Ese código no es correcto. Revísalo e inténtalo otra vez.")
    pending.used_at = utcnow()
    if purpose == PURPOSE_VERIFY_EMAIL:
        user.email_verified_at = utcnow()
    db.session.commit()

"""Registro e inicio de sesión."""

from enum import Enum

from flask import current_app

from ...constants import PURPOSE_RESET_PASSWORD, ROLE_SELLER
from ...extensions import db
from ...models import User
from ...services import verification
from ...services.places import resolve_village
from ...utils import normalize_email, normalize_phone, utcnow


class LoginResult(Enum):
    OK = "ok"
    LOCKED = "locked"
    DISABLED = "disabled"
    INVALID = "invalid"


def register_user(form) -> User:
    """Crea la cuenta con la aceptación de términos registrada (Ley 1581)."""
    village, village_other, _ = resolve_village(
        form.village_id.data, form.village_other.data, form.municipality_id.data
    )
    user = User(
        name=form.name.data.strip(),
        phone=normalize_phone(form.phone.data),
        email=normalize_email(form.email.data),
        role=ROLE_SELLER,  # todos pueden comprar y vender
        municipality_id=form.municipality_id.data,
        village=village,
        village_other=village_other,
        farm_name=(form.farm_name.data or "").strip() or None,
        terms_accepted_at=utcnow(),
        terms_version=current_app.config["LEGAL_VERSION"],
    )
    user.set_password(form.password.data)
    db.session.add(user)
    db.session.commit()
    return user


def find_login_user(identifier: str | None) -> User | None:
    """La cuenta que corresponde a lo escrito en «Celular». Las personas entran con su celular; solo un
    administrador puede tener un usuario escrito (p. ej. «admin»), que se compara sin importar mayúsculas."""
    phone = normalize_phone(identifier)
    if phone:
        return User.by_phone(phone)
    alias = (identifier or "").strip().lower()
    user = User.by_phone(alias)
    return user if user and user.is_admin else None


def authenticate(phone_raw: str, password: str) -> tuple[LoginResult, User | None]:
    """Valida credenciales llevando la cuenta de intentos fallidos y el bloqueo temporal."""
    user = find_login_user(phone_raw)
    if user and user.is_locked():
        return LoginResult.LOCKED, None
    if user and user.check_password(password):
        if not user.is_enabled:  # solo quien tiene la clave correcta se entera de que su cuenta fue suspendida
            return LoginResult.DISABLED, None
        user.register_success()
        db.session.commit()
        return LoginResult.OK, user
    if user:
        user.register_failure()
        db.session.commit()
    return LoginResult.INVALID, None


def request_password_reset(phone_raw: str) -> None:
    """Envía el código de recuperación al correo verificado de la cuenta, si existe.

    Nunca dice si el celular está registrado (evita que alguien averigüe quién tiene cuenta)."""
    user = User.by_phone(normalize_phone(phone_raw))
    if not (user and user.is_enabled and user.email_verified):
        return
    try:
        verification.send_code(user, PURPOSE_RESET_PASSWORD)
    except verification.VerificationError as error:
        current_app.logger.info("Recuperación de clave no enviada (usuario %s): %s", user.id, error)


def reset_password(phone_raw: str, code: str, new_password: str) -> None:
    """Cambia la contraseña si el código es correcto. Lanza VerificationError con un mensaje claro si no."""
    user = User.by_phone(normalize_phone(phone_raw))
    if not (user and user.is_enabled and user.email_verified):
        raise verification.VerificationError("El código venció o no es correcto. Pide uno nuevo.")
    verification.confirm_code(user, code, PURPOSE_RESET_PASSWORD)
    user.set_password(new_password)
    user.register_success()  # quita bloqueos por intentos fallidos
    db.session.commit()

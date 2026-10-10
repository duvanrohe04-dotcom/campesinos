"""Helpers compartidos para formularios Flask-WTF."""

from flask_wtf import FlaskForm
from wtforms import Field, ValidationError

from .models import User
from .utils import normalize_email


class BaseForm(FlaskForm):
    """Base de todos los formularios: mensajes de WTForms en español (sin textos técnicos en inglés)."""

    class Meta(FlaskForm.Meta):
        locales = ["es"]


def validate_optional_email(field: Field, own_user_id: int | None = None) -> None:
    """Un correo es opcional; si lo escriben debe ser válido y no estar en otra cuenta."""
    raw = (field.data or "").strip()
    if not raw:
        return
    email = normalize_email(raw)
    if not email:
        raise ValidationError("Escribe un correo válido. Ej: nombre@gmail.com")
    owner = User.by_email(email)
    if owner and owner.id != own_user_id:
        raise ValidationError("Ese correo ya está en otra cuenta.")


def form_errors(form: FlaskForm) -> dict[str, str]:
    """Primer error de cada campo: {campo: mensaje}. Para las macros de plantilla."""
    return {name: messages[0] for name, messages in form.errors.items() if messages}


def form_values(form: FlaskForm) -> dict[str, str]:
    """Valores actuales de cada campo como texto. Para las macros de plantilla."""
    return {field.name: "" if field.data is None else str(field.data) for field in form if field.name != "csrf_token"}

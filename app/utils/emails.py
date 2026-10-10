"""Correos electrónicos."""

import re

from ..constants import EMAIL_MAX

_EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)*\.[a-z]{2,}$")


def normalize_email(raw: str | None) -> str | None:
    """Devuelve el correo en minúsculas y sin espacios, o None si está vacío o no tiene forma de correo."""
    email = (raw or "").strip().lower()
    return email if email and len(email) <= EMAIL_MAX and _EMAIL_RE.match(email) else None

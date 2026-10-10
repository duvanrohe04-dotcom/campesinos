"""Seguridad de redirecciones."""

from urllib.parse import urlparse


def is_safe_next(target: str | None) -> bool:
    """True si `target` es una ruta relativa interna (evita redirecciones abiertas)."""
    if not target:
        return False
    parts = urlparse(target)
    return not parts.netloc and not parts.scheme and target.startswith("/") and not target.startswith("//")

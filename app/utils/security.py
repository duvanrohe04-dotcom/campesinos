"""Seguridad de redirecciones."""

from urllib.parse import urlparse


def is_safe_next(target: str | None) -> bool:
    """True si `target` es una ruta relativa interna (evita redirecciones abiertas)."""
    if not target or "\\" in target or any(ord(char) < 32 for char in target):
        return False  # los navegadores tratan «/\» como «//» y quitan los caracteres de control
    parts = urlparse(target)
    return not parts.netloc and not parts.scheme and target.startswith("/") and not target.startswith("//")

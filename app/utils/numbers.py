"""Teléfonos y números."""

import re


def normalize_phone(raw: str | None) -> str | None:
    """Devuelve 10 dígitos de celular colombiano (3XXXXXXXXX) o None."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("57") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("3"):
        return digits
    return None


def parse_int(raw: str, minimum: int | None = None, maximum: int | None = None) -> int:
    """Convierte '1.200.000' / '$ 1,200,000' en int. Lanza ValueError con mensaje en español si no es válido."""
    cleaned = re.sub(r"[\s$.,]", "", str(raw))
    if not cleaned.isdigit():
        raise ValueError("Escribe solo números.")
    value = int(cleaned)
    if minimum is not None and value < minimum:
        raise ValueError(f"Debe ser al menos {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError("El número es demasiado grande.")
    return value

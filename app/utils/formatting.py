"""Formato de precios y enlaces de WhatsApp."""

from urllib.parse import quote


def cop(value: int | None) -> str:
    """Pesos colombianos con separador de miles: $ 1.250.000."""
    if value is None:
        return ""
    return "$ " + f"{int(value):,}".replace(",", ".")


def format_phone(phone: str) -> str:
    """3101234567 → 310 123 4567."""
    return f"{phone[:3]} {phone[3:6]} {phone[6:]}" if len(phone) == 10 else phone


def mask_phone(phone: str) -> str:
    """3101234567 → 310 ••• ••67 (el número completo solo se muestra al tocar «Ver celular»)."""
    return f"{phone[:3]} ••• ••{phone[-2:]}" if len(phone) == 10 else "••••••••••"


def place_text(village: str | None, village_other: str | None, municipality: str | None) -> str:
    """«Vereda, Municipio»; si escribieron otra vereda se usa ese nombre."""
    return ", ".join(p for p in (village or village_other, municipality) if p)


def whatsapp_url(phone: str, text: str = "") -> str:
    """Enlace wa.me con mensaje prellenado. Si `phone` está vacío, deja elegir el contacto."""
    base = f"https://wa.me/57{phone}" if phone else "https://wa.me/"
    return f"{base}?text={quote(text)}"

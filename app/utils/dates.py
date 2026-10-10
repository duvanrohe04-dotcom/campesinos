"""Fechas y tiempos relativos."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Fecha/hora UTC sin tzinfo (compatible con SQLite y PostgreSQL)."""
    return datetime.now(UTC).replace(tzinfo=None)


def timeago(dt: datetime | None) -> str:
    """Texto relativo en español: «hace 2 horas»."""
    if not dt:
        return ""
    secs = int((utcnow() - dt).total_seconds())
    if secs < 60:
        return "hace un momento"
    for limit, unit, size in ((3600, "minuto", 60), (86400, "hora", 3600), (86400 * 30, "día", 86400)):
        if secs < limit:
            n = secs // size
            return f"hace {n} {unit}{'s' if n > 1 else ''}"
    return "el " + dt.strftime("%d/%m/%Y")

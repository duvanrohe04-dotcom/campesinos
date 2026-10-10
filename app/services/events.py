"""Agenda del campo: próximos eventos, calendario mensual y exportación .ics."""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import joinedload

from ..constants import EVENT_KINDS, ICS_LINE_LIMIT
from ..extensions import db
from ..models import Event
from ..utils import utcnow


def local_now() -> datetime:
    """Hora actual en Colombia (UTC-5, sin horario de verano)."""
    return utcnow() - timedelta(hours=5)


def _published():
    return Event.query.options(joinedload(Event.municipality)).filter(Event.is_published.is_(True))


def upcoming(limit: int = 10, kind: str | None = None) -> list[Event]:
    """Eventos que aún no terminan, del más próximo al más lejano."""
    now = local_now()
    query = _published().filter(db.func.coalesce(Event.ends_at, Event.starts_at) >= now)
    if kind in EVENT_KINDS:
        query = query.filter(Event.kind == kind)
    return query.order_by(Event.starts_at.asc()).limit(limit).all()


def next_event() -> Event | None:
    events = upcoming(1)
    return events[0] if events else None


@dataclass
class MonthView:
    year: int
    month: int
    title: str
    weeks: list[list[date]]
    events_by_day: dict[date, list[Event]]
    previous: str
    following: str


MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]  # fmt: skip


def parse_month(raw: str | None) -> tuple[int, int]:
    """'2026-10' → (2026, 10). Si es inválido, el mes actual."""
    today = local_now().date()
    try:
        year, month = (int(part) for part in (raw or "").split("-"))
        if 2000 <= year <= 2100 and 1 <= month <= 12:
            return year, month
    except ValueError:
        pass
    return today.year, today.month


def _shift(year: int, month: int, delta: int) -> str:
    index = year * 12 + (month - 1) + delta
    return f"{index // 12}-{index % 12 + 1:02d}"


def month_view(year: int, month: int, kind: str | None = None) -> MonthView:
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    first, last = weeks[0][0], weeks[-1][-1]
    start = datetime.combine(first, datetime.min.time())
    end = datetime.combine(last + timedelta(days=1), datetime.min.time())
    query = _published().filter(Event.starts_at < end, db.func.coalesce(Event.ends_at, Event.starts_at) >= start)
    if kind in EVENT_KINDS:
        query = query.filter(Event.kind == kind)
    events = query.order_by(Event.starts_at.asc()).all()
    by_day: dict[date, list[Event]] = {}
    for event in events:
        day = max(event.starts_at.date(), first)
        while day <= min(event.last_day, last):
            by_day.setdefault(day, []).append(event)
            day += timedelta(days=1)
    return MonthView(year, month, f"{MONTHS_ES[month - 1].capitalize()} de {year}", weeks, by_day,
                     _shift(year, month, -1), _shift(year, month, 1))  # fmt: skip


# ---------------------------------------------------------------- .ics
def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Parte líneas largas (máximo 75 bytes por línea según RFC 5545)."""
    out, current = [], ""
    for char in line:
        if len((current + char).encode("utf-8")) > ICS_LINE_LIMIT:
            out.append(current)
            current = " " + char
        else:
            current += char
    out.append(current)
    return "\r\n".join(out)


def build_ics(event: Event, url: str, domain: str, site_name: str) -> str:
    """Archivo .ics (hora local «flotante»: se muestra a la hora indicada en el calendario del celular)."""
    fmt = "%Y%m%dT%H%M%S"
    end = event.ends_at or event.starts_at + timedelta(hours=2)
    location = ", ".join(p for p in (event.place, event.municipality.name if event.municipality else None) if p)
    parts = [
        event.description or "",
        f"Organiza: {event.organizer}" if event.organizer else "",
        f"Más información: {url}",
    ]
    description = "\n\n".join(p for p in parts if p)
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{site_name}//Agenda del campo//ES", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT", f"UID:evento-{event.id}@{domain}", f"DTSTAMP:{utcnow().strftime(fmt)}Z",
        f"DTSTART:{event.starts_at.strftime(fmt)}", f"DTEND:{end.strftime(fmt)}", f"SUMMARY:{_escape(event.title)}",
        f"DESCRIPTION:{_escape(description)}", f"LOCATION:{_escape(location)}", f"URL:{url}", "END:VEVENT",
        "END:VCALENDAR",
    ]  # fmt: skip
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"

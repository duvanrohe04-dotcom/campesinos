"""Estadísticas por día: registro de vistas/contactos y series para el gráfico del panel."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func

from ..constants import CLICK_WHATSAPP
from ..extensions import db
from ..models import DailyStat, Listing, User
from ..utils import utcnow

WEEK_DAYS = 7


def _today_row(listing_id: int) -> DailyStat:
    today = utcnow().date()
    row = db.session.get(DailyStat, (listing_id, today))
    if not row:
        row = DailyStat(listing_id=listing_id, day=today, views=0, whatsapp=0, calls=0)
        db.session.add(row)
    return row


def record_view(listing: Listing) -> None:
    """Suma una vista al día de hoy (no hace commit)."""
    row = _today_row(listing.id)
    row.views += 1


def record_contact(listing: Listing, kind: str) -> None:
    """Suma un contacto (WhatsApp o llamada) al día de hoy (no hace commit)."""
    row = _today_row(listing.id)
    if kind == CLICK_WHATSAPP:
        row.whatsapp += 1
    else:
        row.calls += 1


@dataclass
class WeeklySeries:
    labels: list[str]
    views: list[int]
    contacts: list[int]

    @property
    def total_views(self) -> int:
        return sum(self.views)

    @property
    def total_contacts(self) -> int:
        return sum(self.contacts)


def weekly_series(user: User, today: date | None = None) -> WeeklySeries:
    """Vistas y contactos por día de los últimos 7 días (hoy incluido) de todos los anuncios del vendedor."""
    today = today or utcnow().date()
    start = today - timedelta(days=WEEK_DAYS - 1)
    rows = (
        db.session.query(DailyStat.day, func.sum(DailyStat.views), func.sum(DailyStat.whatsapp + DailyStat.calls))
        .join(Listing, Listing.id == DailyStat.listing_id)
        .filter(Listing.user_id == user.id, DailyStat.day >= start, DailyStat.day <= today)
        .group_by(DailyStat.day)
        .all()
    )
    by_day = {day: (int(views or 0), int(contacts or 0)) for day, views, contacts in rows}
    days = [start + timedelta(days=i) for i in range(WEEK_DAYS)]
    return WeeklySeries(
        labels=[d.strftime("%d/%m") for d in days],
        views=[by_day.get(d, (0, 0))[0] for d in days],
        contacts=[by_day.get(d, (0, 0))[1] for d in days],
    )

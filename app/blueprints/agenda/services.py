"""Armado de las pantallas de la agenda."""

from dataclasses import dataclass

from flask import current_app, request

from ...constants import EVENT_KINDS
from ...models import Event
from ...services import events as event_service
from ...services.events import MonthView
from ...templating import event_url


@dataclass
class AgendaPage:
    month: MonthView
    upcoming: list[Event]
    kind: str


def agenda_page(month_arg: str | None, kind: str | None) -> AgendaPage:
    year, month = event_service.parse_month(month_arg)
    kind = kind if kind in EVENT_KINDS else ""
    return AgendaPage(
        event_service.month_view(year, month, kind or None), event_service.upcoming(20, kind or None), kind
    )


def get_published_event(event_id: int) -> Event | None:
    event = Event.query.get(event_id)
    return event if event and event.is_published else None


def ics_for(event: Event) -> str:
    domain = request.host.split(":")[0]
    return event_service.build_ics(event, event_url(event, external=True), domain, current_app.config["SITE_NAME"])

"""Lógica de alertas del blueprint: convertir el formulario en búsqueda guardada y armar las pantallas."""

from urllib.parse import parse_qsl

from ...models import Notification, SavedSearch, User
from ...services import notifications, saved_searches


def parse_query_string(raw: str) -> dict[str, str]:
    return dict(parse_qsl(raw or "", keep_blank_values=False))


def user_searches(user: User) -> list[SavedSearch]:
    return user.saved_searches.order_by(SavedSearch.created_at.desc()).all()


def notification_center(user: User) -> list[Notification]:
    return notifications.list_for(user)


def save_from_form(user: User, raw_query: str) -> SavedSearch:
    return saved_searches.save_search(user, parse_query_string(raw_query))

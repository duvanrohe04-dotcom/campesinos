"""Búsquedas guardadas y revisión de coincidencias nuevas (para ejecutar con cron)."""

from collections.abc import Mapping

from flask import current_app

from ..constants import (
    MAX_NOTIFICATIONS_PER_SEARCH_RUN,
    MAX_SAVED_SEARCHES,
    NOTIF_SEARCH_MATCH,
    SAVED_SEARCH_KEYS,
    SAVED_SEARCH_PREFIX,
)
from ..extensions import db
from ..models import Listing, SavedSearch, User
from ..templating import listing_url
from ..utils import utcnow
from .notifications import notify
from .search import search


class SavedSearchError(ValueError):
    """Error con mensaje en español para mostrar al usuario."""


def clean_filters(args: Mapping[str, str]) -> dict[str, str]:
    """Solo conserva los filtros conocidos y con valor (sin página ni orden)."""
    keep = {}
    for key, value in args.items():
        value = (value or "").strip()
        if value and (key in SAVED_SEARCH_KEYS or key.startswith(SAVED_SEARCH_PREFIX)):
            keep[key] = value[:80]
    return keep


def describe(filters: Mapping[str, str]) -> str:
    """Nombre legible a partir de los chips del listado: «Cerdos de engorde · Vélez · Hasta $ 800.000»."""
    _, info = search(filters)
    return " · ".join(label for label, _ in info.chips)[:160] or "Todos los anuncios"


def save_search(user: User, args: Mapping[str, str]) -> SavedSearch:
    filters = clean_filters(args)
    if not filters:
        raise SavedSearchError("Elige al menos un filtro (categoría, municipio, precio…) antes de guardar.")
    if user.saved_searches.count() >= MAX_SAVED_SEARCHES:
        raise SavedSearchError(f"Puedes guardar hasta {MAX_SAVED_SEARCHES} búsquedas. Borra alguna.")
    existing = next((s for s in user.saved_searches if s.filters == filters), None)
    if existing:
        return existing
    saved = SavedSearch(user_id=user.id, name=describe(filters), filters=filters)
    db.session.add(saved)
    db.session.commit()
    return saved


def delete_search(saved: SavedSearch) -> None:
    db.session.delete(saved)
    db.session.commit()


def new_matches(saved: SavedSearch) -> list[Listing]:
    """Anuncios activos que coinciden con la búsqueda y se publicaron después de la última revisión."""
    query, _ = search(saved.filters)
    return (
        query.filter(Listing.created_at > saved.last_checked_at, Listing.user_id != saved.user_id)
        .limit(MAX_NOTIFICATIONS_PER_SEARCH_RUN)
        .all()
    )


def run_saved_searches() -> int:
    """Revisa todas las búsquedas activas y avisa de coincidencias nuevas. Devuelve cuántos avisos se crearon."""
    created = 0
    now = utcnow()
    # Fuera de una petición (cron) se necesita un contexto para generar las URLs de los anuncios
    with current_app.test_request_context():
        for saved in SavedSearch.query.filter_by(is_active=True).all():
            for listing in new_matches(saved):
                notification = notify(
                    saved.user,
                    NOTIF_SEARCH_MATCH,
                    title=f"Nuevo: {listing.title}",
                    body=f"Coincide con tu búsqueda «{saved.name}». {listing.location_text}.",
                    url=listing_url(listing),
                    listing_id=listing.id,
                    saved_search_id=saved.id,
                )
                created += 1 if notification else 0
            saved.last_checked_at = now
            db.session.commit()
    return created

"""Lógica del listado y detalle públicos, favoritos, clics de contacto y reportes."""

from collections.abc import Mapping, MutableMapping
from typing import Any

from flask import current_app, url_for
from flask_login import current_user
from sqlalchemy.orm import joinedload, selectinload

from ...constants import (
    CLICK_KINDS,
    CLICK_SESSION_MEMORY,
    CLICK_WHATSAPP,
    MAP_MAX_POINTS,
    PRICE_BY_AGREEMENT,
    PUBLIC_STATUSES,
)
from ...extensions import db
from ...models import Favorite, Listing, Report, User
from ...services import geo, stats
from ...services.search import SearchInfo
from ...templating import listing_url
from ...utils import cop, whatsapp_url

PAGINATION_RESET_KEYS = ("page",)


def filter_chip_links(
    info: SearchInfo, args: Mapping[str, str], endpoint: str = "listings.index"
) -> list[tuple[str, str]]:
    """Para cada filtro activo, el enlace que lo quita (chips eliminables)."""
    links = []
    for label, keys in info.chips:
        rest = {k: v for k, v in args.items() if k not in keys and k not in PAGINATION_RESET_KEYS and v}
        links.append((label, url_for(endpoint, **rest)))
    return links


def map_points(info_query) -> list[dict]:
    """Puntos para el mapa: anuncios de la búsqueda con su ubicación aproximada (propia, vereda o municipio)."""
    points = []
    for listing in info_query.limit(MAP_MAX_POINTS * 2):
        point, exact = geo.listing_point(listing)
        if not point:
            continue
        image = listing.main_image
        points.append(
            {
                "id": listing.id,
                "title": listing.title,
                "price": "A convenir" if listing.price is None else cop(listing.price),
                "unit": listing.price_unit if listing.price_unit and listing.price_unit != PRICE_BY_AGREEMENT else "",
                "place": listing.location_text,
                "url": listing_url(listing),
                "image": url_for("static", filename="uploads/" + image.thumb) if image else None,
                "lat": point[0],
                "lng": point[1],
                "exact": exact,
            }
        )
        if len(points) >= MAP_MAX_POINTS:
            break
    return points


def get_listing(listing_id: int) -> Listing | None:
    return (
        Listing.query.options(
            selectinload(Listing.images),
            joinedload(Listing.user),
            joinedload(Listing.municipality),
            joinedload(Listing.village),
        )
        .filter_by(id=listing_id)
        .first()
    )


def can_view(listing: Listing) -> bool:
    """Activos y vendidos son públicos; el resto solo para su dueño o un admin."""
    if listing.status in PUBLIC_STATUSES:
        return True
    return current_user.is_authenticated and (current_user.id == listing.user_id or current_user.is_admin)


def is_owner(listing: Listing) -> bool:
    return current_user.is_authenticated and current_user.id == listing.user_id


def register_view(listing: Listing) -> None:
    if not is_owner(listing):
        listing.views_count = (listing.views_count or 0) + 1
        stats.record_view(listing)
        db.session.commit()


def similar_listings(listing: Listing, limit: int = 4) -> list[Listing]:
    return (
        Listing.public_query()
        .filter(Listing.id != listing.id, Listing.category_id.in_(listing.category.root.family_ids))
        .order_by(
            (Listing.category_id == listing.category_id).desc(),
            (Listing.municipality_id == listing.municipality_id).desc(),
            Listing.created_at.desc(),
        )
        .limit(limit)
        .all()
    )


def whatsapp_link(listing: Listing) -> str:
    text = (
        f"Hola, vi tu anuncio «{listing.title}» en {current_app.config['SITE_NAME']}: "
        f"{listing_url(listing, external=True)} ¿Sigue disponible?"
    )
    return whatsapp_url(listing.user.phone, text)


def is_favorite(listing: Listing) -> bool:
    return current_user.is_authenticated and db.session.get(Favorite, (current_user.id, listing.id)) is not None


def favorite_listings(user: User) -> list[Listing]:
    return (
        Listing.card_query()
        .join(Favorite, Favorite.listing_id == Listing.id)
        .filter(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )


def toggle_favorite(user: User, listing: Listing) -> bool:
    """Alterna el favorito. Devuelve True si quedó guardado."""
    favorite = db.session.get(Favorite, (user.id, listing.id))
    if favorite:
        db.session.delete(favorite)
    else:
        db.session.add(Favorite(user_id=user.id, listing_id=listing.id))
    db.session.commit()
    return favorite is None


def record_click(listing: Listing, kind: str, session: MutableMapping[str, Any]) -> bool:
    """Cuenta un clic de WhatsApp/llamada (una vez por sesión y anuncio; el dueño no cuenta)."""
    if kind not in CLICK_KINDS or is_owner(listing):
        return False
    seen = session.setdefault("clicks", [])
    key = f"{listing.id}:{kind}"
    if key in seen:
        return False
    session["clicks"] = [*seen, key][-CLICK_SESSION_MEMORY:]
    column = "whatsapp_clicks" if kind == CLICK_WHATSAPP else "call_clicks"
    setattr(listing, column, (getattr(listing, column) or 0) + 1)
    stats.record_contact(listing, kind)
    db.session.commit()
    return True


def create_report(listing: Listing, reason: str, detail: str | None) -> Report:
    report = Report(
        listing_id=listing.id,
        reason=reason,
        detail=(detail or "").strip() or None,
        reporter_id=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(report)
    db.session.commit()
    return report

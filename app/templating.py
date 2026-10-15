"""Filtros y globales de Jinja."""

import os

from flask import Flask, current_app, request, url_for
from flask_login import current_user

from .constants import (
    AD_TYPE_SHORT,
    AD_TYPES,
    ATTR_TEXT_MAX,
    BACK_DEFAULT,
    BACK_FALLBACK_EXACT,
    BACK_FALLBACK_PREFIXES,
    CATEGORY_PHOTO_DIR,
    EVENT_KINDS,
    LISTING_STATUSES,
    OTHER_CHOICES,
    VILLAGE_OTHER_ID,
    VILLAGE_OTHER_MAX,
)
from .models import Category, Listing, Municipality
from .services.notifications import unread_count
from .utils import cop, format_phone, mask_phone, timeago, utcnow, whatsapp_url


def listing_url(listing: Listing, external: bool = False) -> str:
    """URL amigable canónica: /<categoría>/<subcategoría>/<slug>-<id>."""
    category = listing.category
    parent = category.parent.slug if category.parent else category.slug
    return url_for(
        "listings.detail", cat=parent, sub=category.slug, slug_id=f"{listing.slug}-{listing.id}", _external=external
    )


def event_url(event, external: bool = False) -> str:
    """URL amigable de un evento: /agenda/<slug>-<id>."""
    return url_for("agenda.detail", slug_id=f"{event.slug}-{event.id}", _external=external)


def back_target(endpoint: str | None) -> str | None:
    """Dirección del botón «Volver» cuando no hay página anterior; None si la página no lleva el botón (el inicio)."""
    if endpoint in BACK_FALLBACK_EXACT:
        target = BACK_FALLBACK_EXACT[endpoint]
    else:
        target = next(
            (to for prefix, to in BACK_FALLBACK_PREFIXES if (endpoint or "").startswith(prefix)), BACK_DEFAULT
        )
    return url_for(target) if target else None


def category_photo(category: Category) -> str | None:
    """Ruta (dentro de static/) de la foto de la categoría raíz, o None si no tiene y se usa el icono."""
    relative = f"{CATEGORY_PHOTO_DIR}/{category.root.slug}.webp"
    return relative if os.path.isfile(os.path.join(current_app.static_folder, relative)) else None


def register_template_helpers(app: Flask) -> None:
    app.jinja_env.filters["cop"] = cop
    app.jinja_env.filters["timeago"] = timeago
    app.jinja_env.filters["phone"] = format_phone
    app.jinja_env.filters["mask_phone"] = mask_phone
    app.jinja_env.filters["zip"] = lambda a, b: list(zip(a, b, strict=False))
    app.jinja_env.globals.update(
        listing_url=listing_url,
        event_url=event_url,
        category_photo=category_photo,
        back_target=back_target,
        ATTR_TEXT_MAX=ATTR_TEXT_MAX,
        OTHER_CHOICES=OTHER_CHOICES,
        VILLAGE_OTHER_ID=VILLAGE_OTHER_ID,
        VILLAGE_OTHER_MAX=VILLAGE_OTHER_MAX,
        whatsapp_url=whatsapp_url,
        AD_TYPES=AD_TYPES,
        AD_TYPE_SHORT=AD_TYPE_SHORT,
        STATUSES=LISTING_STATUSES,
        EVENT_KINDS=EVENT_KINDS,
    )

    @app.context_processor
    def inject_globals() -> dict:
        if request.endpoint and request.endpoint.startswith("static"):
            return {}
        return {
            "now_year": utcnow().year,
            "unread_notifications": unread_count(current_user) if current_user.is_authenticated else 0,
            "nav_categories": Category.active_roots(),
            "nav_municipalities": Municipality.ordered(),
        }

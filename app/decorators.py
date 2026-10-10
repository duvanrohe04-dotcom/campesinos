"""Decoradores y helpers de permisos."""

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import abort
from flask_login import current_user, login_required

from .extensions import db
from .models import Listing


def get_owned_listing(listing_id: int) -> Listing:
    """Devuelve el anuncio si es del usuario actual (o es admin). 404 si no existe, 403 si es ajeno."""
    listing = db.session.get(Listing, listing_id) or abort(404)
    if listing.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return listing


def admin_required(view: Callable) -> Callable:
    """Solo administradores (403 para el resto; anónimos van al login)."""

    @wraps(view)
    @login_required
    def wrapper(*args: Any, **kwargs: Any):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapper


def owner_required(view: Callable) -> Callable:
    """Carga el anuncio `listing_id` y exige que sea del usuario (o admin). Inyecta `listing` en la vista."""

    @wraps(view)
    @login_required
    def wrapper(*args: Any, listing_id: int, **kwargs: Any):
        return view(*args, listing=get_owned_listing(listing_id), **kwargs)

    return wrapper

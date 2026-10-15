"""Panel del vendedor, publicar/editar anuncios, acciones rápidas, perfil propio y perfil público."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import quote

from flask import current_app

from ...constants import (
    AD_TYPES,
    STATUS_ACTIVE,
    STATUS_PAUSED,
    STATUS_REMOVED,
    STATUS_SOLD,
    VILLAGE_OTHER_ID,
)
from ...extensions import db
from ...models import Category, Listing, Municipality, User, VerificationCode, Village
from ...services import images, verification
from ...services.attributes import defs_for
from ...services.expiry import renew
from ...services.listing_form import (
    apply_data,
    apply_images,
    step_for_error,
    values_from_listing,
)
from ...services.places import resolve_village
from ...services.stats import WeeklySeries, weekly_series
from ...templating import listing_url
from ...utils import normalize_email, utcnow

# Acciones rápidas del panel que solo cambian el estado: acción -> (estado nuevo, mensaje)
STATUS_ACTIONS = {
    "pausar": (STATUS_PAUSED, "Anuncio pausado. Nadie lo verá hasta que lo actives."),
    "activar": (STATUS_ACTIVE, "Anuncio activo otra vez."),
    "vendido": (STATUS_SOLD, "¡Felicitaciones por la venta! Quedó marcado como vendido."),
}


@dataclass
class PanelSummary:
    items: list[Listing]
    stats: dict[str, int]
    expiring: list[Listing]
    weekly: WeeklySeries


def panel_summary(user: User) -> PanelSummary:
    items = (
        Listing.card_query()
        .filter(Listing.user_id == user.id, Listing.status != STATUS_REMOVED)
        .order_by(Listing.created_at.desc())
        .all()
    )
    stats = {
        "active": sum(1 for i in items if i.status == STATUS_ACTIVE),
        "views": sum(i.views_count or 0 for i in items),
        "contacts": sum(i.contacts_count for i in items),
        "sold": sum(1 for i in items if i.status == STATUS_SOLD),
    }
    return PanelSummary(
        items=items, stats=stats, expiring=[i for i in items if i.expiring_soon], weekly=weekly_series(user)
    )


def publish_block_reason(user: User) -> str | None:
    """Mensaje si la persona no puede publicar otro anuncio ahora (tope de activos; más bajo en cuentas nuevas)."""
    if user.is_admin:
        return None
    cfg = current_app.config
    active = Listing.query.filter_by(user_id=user.id, status=STATUS_ACTIVE).count()
    is_new = user.created_at and utcnow() - user.created_at < timedelta(hours=cfg["NEW_ACCOUNT_HOURS"])
    if is_new and active >= cfg["NEW_ACCOUNT_MAX_LISTINGS"]:
        return (
            f"Tu cuenta es nueva: por ahora puedes tener hasta {cfg['NEW_ACCOUNT_MAX_LISTINGS']} anuncios activos. "
            "Mañana podrás publicar más."
        )
    if active >= cfg["MAX_ACTIVE_LISTINGS"]:
        return (
            f"Ya tienes {active} anuncios activos, que es el máximo. "
            "Marca como vendido o pausa alguno para poder publicar otro."
        )
    return None


def initial_values(user: User, wanted_type: str = "") -> dict[str, str]:
    """Valores iniciales de un formulario de publicación nuevo."""
    return {
        "municipality_id": str(user.municipality_id or ""),
        "village_id": str(user.village_id or (VILLAGE_OTHER_ID if user.village_other else "")),
        "village_other": user.village_other or "",
        "ad_type": wanted_type if wanted_type in AD_TYPES else "",
    }


def copy_values(source: Listing) -> dict[str, str]:
    return values_from_listing(source)


def listing_form_context(
    user: User, values: dict, errors: dict, listing: Listing | None = None, editing: bool = False
) -> dict[str, Any]:
    """Todo lo que necesita la plantilla del asistente de publicación."""
    roots = Category.active_roots()
    selected_root = None
    if (values.get("category_id") or "").isdigit():
        category = db.session.get(Category, int(values["category_id"]))
        selected_root = category.root.id if category else None
    return {
        "roots": roots,
        "attr_defs": {r.id: defs_for(r) for r in roots},
        "values": values,
        "errors": errors,
        "listing": listing,
        "editing": editing,
        "selected_root": selected_root,
        "municipalities": Municipality.ordered(),
        "villages": Village.ordered(),
        "start_step": step_for_error(errors) if errors else 1,
        "existing_images": [{"id": i.id, "f": i.thumb} for i in listing.images] if listing else [],
    }


def create_listing(user: User, cleaned: dict, form_data, files) -> tuple[Listing | None, str | None]:
    """Crea y guarda el anuncio. Devuelve (anuncio, None) o (None, error_de_fotos)."""
    listing = Listing(user=user, status=STATUS_ACTIVE)
    apply_data(listing, cleaned)
    listing.set_expiry()
    db.session.add(listing)
    db.session.flush()
    photo_errors = apply_images(listing, form_data, files)
    if photo_errors:
        db.session.rollback()
        return None, " ".join(photo_errors)
    db.session.commit()
    return listing, None


def update_listing(listing: Listing, cleaned: dict, form_data, files) -> str | None:
    """Actualiza el anuncio. Devuelve un mensaje de error de fotos o None si salió bien."""
    apply_data(listing, cleaned)
    photo_errors = apply_images(listing, form_data, files)
    if photo_errors:
        db.session.rollback()
        return " ".join(photo_errors)
    db.session.commit()
    return None


def share_link(listing: Listing) -> tuple[str, str]:
    """(enlace del anuncio, enlace de WhatsApp para compartirlo)."""
    url = listing_url(listing, external=True)
    return url, "https://wa.me/?text=" + quote(f"Mira lo que ofrezco: {listing.title}. {url}")


class ActionBlockedError(Exception):
    """La acción no se puede hacer ahora; el mensaje está en español y se muestra al usuario."""


def perform_action(listing: Listing, action: str) -> str:
    """Pausar, activar, vender, renovar o eliminar. Devuelve el mensaje para el usuario.

    Lanza ValueError si la acción no existe o no aplica (un anuncio retirado por el admin solo se puede eliminar) y
    ActionBlockedError si volver a activarlo pasaría el tope de anuncios activos."""
    if listing.status == STATUS_REMOVED and action != "eliminar":
        raise ValueError(f"El anuncio fue retirado: {action}")
    reactivates = action in ("activar", "renovar") and listing.status != STATUS_ACTIVE
    if reactivates and (blocked := publish_block_reason(listing.user)):
        raise ActionBlockedError(blocked)
    if action in STATUS_ACTIONS:
        status, message = STATUS_ACTIONS[action]
        if action == "activar" and listing.expires_at and listing.expires_at < utcnow():
            listing.set_expiry()
        listing.status = status
    elif action == "renovar":
        renew(listing)
        message = "Renovado por 30 días más."
    elif action == "eliminar":
        for image in listing.images:
            images.delete_files(image.filename)
        db.session.delete(listing)
        message = "Anuncio eliminado."
    else:
        raise ValueError(f"Acción desconocida: {action}")
    db.session.commit()
    return message


def _apply_photo(user: User, form, upload) -> str | None:
    """Reemplaza o quita la foto de perfil. Devuelve un mensaje de error si la foto no sirve."""
    if upload and upload.filename:
        try:
            new_photo = images.save_upload(upload)
        except images.ImageError as error:
            return str(error)
        if user.photo:
            images.delete_files(user.photo)
        user.photo = new_photo
    elif form.remove_photo.data and user.photo:
        images.delete_files(user.photo)
        user.photo = None
    return None


def _apply_email(user: User, email: str | None) -> None:
    """Guarda el correo; si cambió, vuelve a estar sin verificar."""
    if email != user.email:
        user.email, user.email_verified_at = email, None
        # Un código enviado al correo anterior no debe servir para verificar el nuevo
        VerificationCode.query.filter_by(user_id=user.id, used_at=None).update({"used_at": utcnow()})


def send_email_verification(user: User) -> str | None:
    """Envía el código al correo sin verificar. Devuelve un mensaje de error, o None si salió bien."""
    try:
        verification.send_code(user)
    except verification.VerificationError as error:
        return str(error)
    return None


def update_profile(user: User, form, upload=None) -> str | None:
    """Guarda el perfil. Devuelve un mensaje de error de la foto, o None si todo salió bien."""
    photo_error = _apply_photo(user, form, upload)
    if photo_error:
        return photo_error
    village, village_other, _ = resolve_village(
        form.village_id.data, form.village_other.data, form.municipality_id.data
    )
    user.name = " ".join(form.name.data.split())
    _apply_email(user, normalize_email(form.email.data))
    user.municipality_id, user.village, user.village_other = form.municipality_id.data, village, village_other
    user.farm_name = (form.farm_name.data or "").strip() or None
    user.bio = (form.bio.data or "").strip() or None
    db.session.commit()
    return None


def get_public_seller(user_id: int) -> User | None:
    """La persona si tiene perfil público: cuenta activa y que no sea de administración."""
    seller = db.session.get(User, user_id)
    return seller if seller and seller.is_enabled and not seller.is_admin else None


def seller_page(user_id: int) -> tuple[User | None, list[Listing], int]:
    seller = get_public_seller(user_id)
    if not seller:
        return None, [], 0
    listings = (
        Listing.card_query()
        .filter_by(user_id=seller.id, status=STATUS_ACTIVE)
        .order_by(Listing.created_at.desc())
        .all()
    )
    sold = Listing.query.filter_by(user_id=seller.id, status=STATUS_SOLD).count()
    return seller, listings, sold

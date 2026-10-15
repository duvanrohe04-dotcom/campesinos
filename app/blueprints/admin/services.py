"""Operaciones del panel de administración (moderación, categorías, atributos, geografía)."""

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ...constants import (
    MESSAGE_NEW,
    MESSAGE_READ,
    REPORT_DISMISSED,
    REPORT_OPEN,
    REPORT_REVIEWED,
    STATUS_ACTIVE,
    STATUS_PAUSED,
    STATUS_REMOVED,
)
from ...extensions import db
from ...models import (
    AttributeDef,
    Category,
    ContactMessage,
    Listing,
    Municipality,
    Report,
    User,
    Village,
)
from ...services import images
from ...utils import slugify, utcnow


@dataclass
class DashboardData:
    counts: dict[str, int]
    latest: list[Listing]


def dashboard_data() -> DashboardData:
    counts = {
        "users": User.query.count(),
        "listings": Listing.query.filter_by(status=STATUS_ACTIVE).count(),
        "reports": Report.query.filter_by(status=REPORT_OPEN).count(),
        "messages": ContactMessage.query.filter_by(status=MESSAGE_NEW).count(),
    }
    latest = Listing.query.options(joinedload(Listing.user)).order_by(Listing.created_at.desc()).limit(8).all()
    return DashboardData(counts, latest)


# ---------- Usuarios ----------
def search_users(text: str, limit: int = 100) -> list[User]:
    query = User.query.order_by(User.created_at.desc())
    if text:
        query = query.filter(User.name.ilike(f"%{text}%") | User.phone.like(f"%{text}%"))
    return query.limit(limit).all()


def toggle_user(user: User) -> bool:
    """Activa/desactiva la cuenta (al desactivar se pausan sus anuncios). Devuelve el nuevo estado."""
    user.is_enabled = not user.is_enabled
    if not user.is_enabled:
        Listing.query.filter_by(user_id=user.id, status=STATUS_ACTIVE).update({"status": STATUS_PAUSED})
    db.session.commit()
    return user.is_enabled


def toggle_verified_seller(user: User) -> bool:
    """Otorga o retira la insignia «Vendedor verificado». Devuelve el nuevo estado."""
    user.is_verified_seller = not user.is_verified_seller
    db.session.commit()
    return user.is_verified_seller


# ---------- Anuncios ----------
def list_listings(status: str, limit: int = 100) -> list[Listing]:
    query = Listing.query.options(joinedload(Listing.user), joinedload(Listing.category)).order_by(
        Listing.created_at.desc()
    )
    if status:
        query = query.filter_by(status=status)
    return query.limit(limit).all()


def moderate_listing(listing: Listing, action: str) -> str:
    """retirar | restaurar | eliminar. Devuelve el mensaje; lanza ValueError si la acción no existe."""
    if action == "retirar":
        listing.status, message = STATUS_REMOVED, "Anuncio retirado."
    elif action == "restaurar":
        listing.status, message = STATUS_ACTIVE, "Anuncio restaurado."
        if not listing.expires_at or listing.expires_at < utcnow():  # si no, el cron lo vencería de inmediato
            listing.set_expiry()
    elif action == "eliminar":
        for image in listing.images:
            images.delete_files(image.filename)
        db.session.delete(listing)
        message = "Anuncio eliminado."
    else:
        raise ValueError(action)
    db.session.commit()
    return message


# ---------- Reportes y mensajes ----------
def list_reports(status: str, limit: int = 100) -> list[Report]:
    return (
        Report.query.options(joinedload(Report.listing), joinedload(Report.reporter))
        .filter_by(status=status)
        .order_by(Report.created_at.desc())
        .limit(limit)
        .all()
    )


def resolve_report(report: Report, action: str) -> str | None:
    """revisado | descartar | retirar (retira el anuncio). Lanza ValueError si la acción no existe."""
    message = None
    if action == "revisado":
        report.status = REPORT_REVIEWED
    elif action == "descartar":
        report.status = REPORT_DISMISSED
    elif action == "retirar":
        report.listing.status, report.status, message = STATUS_REMOVED, REPORT_REVIEWED, "Anuncio retirado."
    else:
        raise ValueError(action)
    db.session.commit()
    return message


def list_messages(status: str, limit: int = 100) -> list[ContactMessage]:
    return ContactMessage.query.filter_by(status=status).order_by(ContactMessage.created_at.desc()).limit(limit).all()


def mark_message_read(message: ContactMessage) -> None:
    message.status = MESSAGE_READ
    db.session.commit()


# ---------- Categorías ----------
def save_category(form, category: Category | None, parent: Category | None) -> Category:
    """Crea o actualiza una categoría/subcategoría con los datos validados del formulario."""
    target = category or Category(parent_id=parent.id if parent else None, slug=slugify(form.name.data))
    target.name = form.name.data.strip()
    target.icon = form.icon.data or "campo"
    target.position = form.position.data or 0
    target.is_active = form.is_active.data
    if not target.parent_id:  # solo las categorías raíz tienen unidades, sección de inicio y aviso ICA
        target.home_section = form.home_section.data or None
        target.requires_ica = form.requires_ica.data
        target.price_units = [u.strip() for u in (form.price_units.data or "").split(",") if u.strip()]
    db.session.add(target)
    db.session.commit()
    return target


def category_form_defaults(category: Category) -> dict:
    return {
        "name": category.name,
        "icon": category.icon,
        "position": category.position,
        "home_section": category.home_section or "",
        "requires_ica": category.requires_ica,
        "is_active": category.is_active,
        "price_units": ", ".join(category.price_units or []),
    }


def delete_category(category: Category) -> bool:
    """Elimina solo si no tiene subcategorías ni publicaciones. Devuelve si se eliminó."""
    if category.children or Listing.query.filter_by(category_id=category.id).count():
        return False
    db.session.delete(category)
    try:
        db.session.commit()
    except IntegrityError:  # aún la usan otros datos (p. ej. precios de referencia históricos)
        db.session.rollback()
        return False
    return True


# ---------- Atributos ----------
def save_attribute(form, category: Category, attr: AttributeDef | None) -> AttributeDef:
    target = attr or AttributeDef(category_id=category.id, key=form.computed_key)
    target.label, target.type = form.label.data.strip(), form.type.data
    target.required = form.required.data
    target.choices = form.option_list() if form.type.data == "choice" else None
    target.min_value, target.max_value = form.min_number, form.max_number
    target.unit = (form.unit.data or "").strip() or None
    target.help_text = (form.help_text.data or "").strip() or None
    target.is_filterable = form.is_filterable.data
    target.is_active = form.is_active.data if attr else True
    target.position = form.position.data if form.position.data is not None else len(category.attribute_defs)
    db.session.add(target)
    db.session.commit()
    return target


def attribute_form_defaults(attr: AttributeDef) -> dict:
    return {
        "label": attr.label,
        "key": attr.key,
        "type": attr.type,
        "required": attr.required,
        "choices": ", ".join(attr.choices or []),
        "unit": attr.unit or "",
        "help_text": attr.help_text or "",
        "min_value": "" if attr.min_value is None else f"{attr.min_value:g}",
        "max_value": "" if attr.max_value is None else f"{attr.max_value:g}",
        "is_filterable": attr.is_filterable,
        "position": attr.position,
        "is_active": attr.is_active,
    }


# ---------- Municipios y veredas ----------
def municipalities_with_counts() -> list[tuple[Municipality, int]]:
    return (
        db.session.query(Municipality, func.count(Village.id))
        .outerjoin(Village)
        .group_by(Municipality.id)
        .order_by(Municipality.name)
        .all()
    )


def add_municipality(name: str, department: str | None) -> Municipality | None:
    """Devuelve el municipio o None si ya existía."""
    name = name.strip()
    if Municipality.query.filter_by(slug=slugify(name)).first():
        return None
    municipality = Municipality(name=name, slug=slugify(name), department=(department or "Santander").strip())
    db.session.add(municipality)
    db.session.commit()
    return municipality


def set_center(place: Municipality | Village, point: tuple[float, float] | None) -> None:
    """Guarda (o borra, si `point` es None) el centro aproximado de un municipio o vereda."""
    place.lat, place.lng = point if point else (None, None)
    db.session.commit()


def add_village(municipality: Municipality, name: str) -> bool:
    name = name.strip()
    if Village.query.filter_by(municipality_id=municipality.id, name=name).first():
        return False
    db.session.add(Village(municipality_id=municipality.id, name=name))
    db.session.commit()
    return True


def delete_village(village: Village) -> bool:
    """No elimina veredas en uso. Devuelve si se eliminó."""
    in_use = (
        Listing.query.filter_by(village_id=village.id).count() or User.query.filter_by(village_id=village.id).count()
    )
    if in_use:
        return False
    db.session.delete(village)
    db.session.commit()
    return True

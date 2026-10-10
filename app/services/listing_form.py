"""Validación del formulario de publicación (campos comunes + atributos de categoría) y manejo de fotos."""

from collections.abc import Mapping
from datetime import date
from typing import Any

from flask import current_app
from werkzeug.datastructures import MultiDict

from ..constants import (
    AD_BUY,
    AD_TYPES,
    DESCRIPTION_MAX,
    PRICE_BY_AGREEMENT,
    PRICE_MAX,
    QUANTITY_MAX,
    TITLE_MAX,
    TITLE_MIN,
    VILLAGE_OTHER_ID,
)
from ..extensions import db
from ..models import Category, Listing, ListingImage, Municipality, User
from ..utils import parse_int
from . import geo, images
from .attributes import form_values_from_attrs, validate_attrs
from .places import resolve_village

# Paso del asistente donde vive cada campo (para abrir el paso con error)
STEP_OF = {
    "ad_type": 1, "category_id": 1, "title": 1,
    "description": 2, "quantity": 2, "photos": 3,
    "price": 4, "price_unit": 4, "municipality_id": 4, "village_id": 4, "village_other": 4,
    "available_from": 4, "lat": 4,
}  # fmt: skip


def step_for_error(errors: Mapping[str, str]) -> int:
    steps = [2 if key.startswith("attr_") else STEP_OF.get(key, 4) for key in errors]
    return min(steps) if steps else 1


def values_from_listing(listing: Listing) -> dict[str, str]:
    """Valores de formulario (texto) a partir de un anuncio existente: para editar o duplicar."""
    values = {
        "ad_type": listing.ad_type,
        "category_id": str(listing.category_id),
        "title": listing.title,
        "description": listing.description or "",
        "price": str(listing.price) if listing.price is not None else "",
        "price_unit": listing.price_unit or "",
        "negotiable": "1" if listing.negotiable else "",
        "quantity": str(listing.quantity) if listing.quantity else "",
        "available_from": listing.available_from.isoformat() if listing.available_from else "",
        "municipality_id": str(listing.municipality_id),
        "village_id": str(listing.village_id or (VILLAGE_OTHER_ID if listing.village_other else "")),
        "village_other": listing.village_other or "",
        "lat": "" if listing.lat is None else str(listing.lat),
        "lng": "" if listing.lng is None else str(listing.lng),
    }
    values.update(form_values_from_attrs(listing.category, listing.attrs))
    return values


def _parse_category(form: Mapping[str, str], errors: dict[str, str]) -> Category | None:
    raw = form.get("category_id", "")
    category = db.session.get(Category, int(raw)) if raw.isdigit() else None
    if not category or not category.is_active:
        errors["category_id"] = "Elige qué tipo de producto es."
        return None
    if not category.parent_id and category.active_children:
        errors["category_id"] = "Elige también el tipo exacto (por ejemplo: Vacas, Toros…)."
    return category


def _parse_title(form: Mapping[str, str], errors: dict[str, str]) -> str:
    title = " ".join((form.get("title") or "").split())
    if not TITLE_MIN <= len(title) <= TITLE_MAX:
        errors["title"] = f"Escribe un título de {TITLE_MIN} a {TITLE_MAX} letras. Ej: Novillo cebú de 18 meses."
    return title


def _parse_price(form: Mapping[str, str], category: Category | None, ad_type: str, errors: dict[str, str]):
    unit = form.get("price_unit", "")
    if category and unit not in category.units:
        errors["price_unit"] = "Elige cómo cobras (por kilo, por cabeza…)."
    price = None
    raw = (form.get("price") or "").strip()
    if raw:
        try:
            price = parse_int(raw, 0, PRICE_MAX)
        except ValueError as e:
            errors["price"] = str(e)
    elif unit != PRICE_BY_AGREEMENT and ad_type != AD_BUY:
        errors["price"] = "Escribe el precio, o elige «a convenir»."
    return price, unit


def _parse_quantity(form: Mapping[str, str], errors: dict[str, str]) -> int | None:
    raw = (form.get("quantity") or "").strip()
    if not raw:
        return None
    try:
        return parse_int(raw, 1, QUANTITY_MAX)
    except ValueError as e:
        errors["quantity"] = str(e)
        return None


def _parse_date(form: Mapping[str, str], errors: dict[str, str]) -> date | None:
    raw = (form.get("available_from") or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        errors["available_from"] = "La fecha no es válida."
        return None


def _parse_place(form: Mapping[str, str], errors: dict[str, str]):
    municipality = None
    if (form.get("municipality_id") or "").isdigit():
        municipality = db.session.get(Municipality, int(form["municipality_id"]))
    if not municipality:
        errors["municipality_id"] = "Elige el municipio."
    raw_village = form.get("village_id") or ""
    village, village_other, error = resolve_village(
        int(raw_village) if raw_village.isdigit() else None,
        form.get("village_other"),
        municipality.id if municipality else None,
    )
    if error:
        errors[error[0]] = error[1]
    return municipality, village, village_other


def _parse_point(form: Mapping[str, str], errors: dict[str, str]):
    try:
        return geo.parse_point(form.get("lat"), form.get("lng"))
    except ValueError as error:
        errors["lat"] = str(error)
        return None


def parse_listing_form(form: Mapping[str, str], user: User) -> tuple[dict[str, Any], dict[str, str]]:
    """Devuelve (datos, errores). `datos` solo es confiable si `errores` está vacío."""
    errors: dict[str, str] = {}
    ad_type = form.get("ad_type", "")
    if ad_type not in AD_TYPES:
        errors["ad_type"] = "Elige qué quieres hacer."

    category = _parse_category(form, errors)
    title = _parse_title(form, errors)
    description = (form.get("description") or "").strip()
    if len(description) > DESCRIPTION_MAX:
        errors["description"] = f"La descripción es muy larga (máximo {DESCRIPTION_MAX} letras)."

    attrs: dict[str, Any] = {}
    if category:
        attrs, attr_errors = validate_attrs(category, form)
        errors.update(attr_errors)

    price, unit = _parse_price(form, category, ad_type, errors)
    municipality, village, village_other = _parse_place(form, errors)
    point = _parse_point(form, errors)
    data = {
        "ad_type": ad_type, "category": category, "title": title, "description": description or None,
        "attrs": attrs, "quantity": _parse_quantity(form, errors), "price": price, "price_unit": unit,
        "negotiable": form.get("negotiable") == "1", "available_from": _parse_date(form, errors),
        "municipality": municipality, "village": village, "village_other": village_other,
        "lat": point[0] if point else None, "lng": point[1] if point else None,
    }  # fmt: skip
    return data, errors


def apply_data(listing: Listing, data: Mapping[str, Any]) -> None:
    """Copia los datos validados al modelo."""
    for field in ("ad_type", "category", "title", "description", "attrs", "quantity", "price", "price_unit",
                  "negotiable", "available_from", "municipality", "village", "village_other",
                  "lat", "lng"):  # fmt: skip
        setattr(listing, field, data[field])


def _image_plan(listing: Listing, form: Mapping[str, str], new_files: list) -> list:
    """Orden final de fotos: tokens eN (existente) y nN (nueva). Sin JavaScript se conservan y se agregan las nuevas."""
    if form.get("image_order_set") == "1":
        tokens = [t for t in form.get("image_order", "").split(",") if t]
    else:
        tokens = [f"e{i.id}" for i in listing.images] + [f"n{i}" for i in range(len(new_files))]
    existing = {i.id: i for i in listing.images}
    plan, seen = [], set()
    for token in tokens:
        if token in seen or len(token) < 2 or not token[1:].isdigit():
            continue
        seen.add(token)
        n = int(token[1:])
        if token[0] == "e" and n in existing:
            plan.append(existing[n])
        elif token[0] == "n" and n < len(new_files):
            plan.append(new_files[n])
    return plan


def apply_images(listing: Listing, form: Mapping[str, str], files: MultiDict) -> list[str]:
    """Aplica orden/eliminación de fotos existentes y guarda las nuevas. Devuelve la lista de errores."""
    max_images = current_app.config["MAX_IMAGES"]
    new_files = [f for f in files.getlist("photos") if f and f.filename]
    plan = _image_plan(listing, form, new_files)
    if len(plan) > max_images:
        return [f"Puedes subir máximo {max_images} fotos."]

    saved: list[ListingImage] = []
    errors: list[str] = []
    for item in plan:
        if isinstance(item, ListingImage):
            saved.append(item)
            continue
        try:
            saved.append(ListingImage(filename=images.save_upload(item)))
        except images.ImageError as e:
            errors.append(f"{item.filename}: {e}")
    if errors:
        for image in saved:
            if image.id is None:
                images.delete_files(image.filename)
        return errors

    keep = {id(s) for s in saved}
    for image in list(listing.images):
        if id(image) not in keep:
            listing.images.remove(image)
            images.delete_files(image.filename)
    listing.images[:] = saved
    for position, image in enumerate(listing.images):
        image.position = position
    return []

"""Búsqueda y filtros del listado público (incluye filtros por atributos JSON)."""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, or_

from ..constants import AD_TYPES, SEARCH_TEXT_MAX
from ..extensions import db
from ..models import AttributeDef, Category, Listing, Municipality, Village
from .attributes import defs_for
from .geo import listing_ids_near, parse_near

SORTS: dict[str, tuple[str, Callable[[], Any]]] = {
    "recientes": ("Más recientes", lambda: Listing.created_at.desc()),
    "precio_asc": ("Precio: menor a mayor", lambda: Listing.price.asc()),
    "precio_desc": ("Precio: mayor a menor", lambda: Listing.price.desc()),
}


@dataclass
class SearchInfo:
    """Resultado de interpretar los filtros: lo que la plantilla necesita para pintar chips y controles."""

    chips: list[tuple[str, list[str]]] = field(default_factory=list)  # (etiqueta, claves a quitar)
    root: Category | None = None
    sub: Category | None = None
    defs: list[AttributeDef] = field(default_factory=list)
    order: str = "recientes"
    near: tuple[float, float] | None = None
    radius: int | None = None


def _num(raw: str) -> float | None:
    try:
        value = float(str(raw).replace(".", "").replace(",", "."))
    except ValueError:
        return None
    return value if math.isfinite(value) else None  # «nan» e «inf» no son números de búsqueda


def filterable_defs(category: Category | None) -> list[AttributeDef]:
    return [d for d in defs_for(category) if d.is_filterable] if category else []


def _apply_category(q, args: Mapping[str, str], info: SearchInfo):
    if args.get("cat"):
        info.root = Category.root_by_slug(args["cat"])
    if args.get("sub"):
        info.sub = Category.sub_by_slug(args["sub"])
        if info.sub and not info.root:
            info.root = info.sub.parent
    if info.sub:
        info.chips.append((info.sub.name, ["sub"]))
        return q.filter(Listing.category_id == info.sub.id)
    if info.root:
        info.chips.append((info.root.name, ["cat", "sub"]))
        return q.filter(Listing.category_id.in_(info.root.family_ids))
    return q


def _apply_text(q, args: Mapping[str, str], info: SearchInfo):
    text = (args.get("q") or "").strip()[:SEARCH_TEXT_MAX]
    if not text:
        return q
    for word in text.split():
        like = f"%{word.replace('%', '').replace('_', '')}%"
        q = q.filter(or_(Listing.title.ilike(like), Listing.description.ilike(like)))
    info.chips.append((f"«{text}»", ["q"]))
    return q


def _apply_place(q, args: Mapping[str, str], info: SearchInfo):
    if not (args.get("mun") or "").isdigit():
        return q
    municipality = db.session.get(Municipality, int(args["mun"]))
    if not municipality:
        return q
    q = q.filter(Listing.municipality_id == municipality.id)
    info.chips.append((municipality.name, ["mun", "ver"]))
    if (args.get("ver") or "").isdigit():
        village = db.session.get(Village, int(args["ver"]))
        if village and village.municipality_id == municipality.id:
            q = q.filter(Listing.village_id == village.id)
            info.chips.append((f"Vereda {village.name}", ["ver"]))
    return q


def _apply_price(q, args: Mapping[str, str], info: SearchInfo):
    low, high = _num(args.get("pmin", "")), _num(args.get("pmax", ""))
    if low is not None:
        q = q.filter(Listing.price >= low)
        info.chips.append((f"Desde $ {int(low):,}".replace(",", "."), ["pmin"]))
    if high is not None:
        q = q.filter(Listing.price <= high)
        info.chips.append((f"Hasta $ {int(high):,}".replace(",", "."), ["pmax"]))
    return q


def _apply_range(q, d: AttributeDef, args: Mapping[str, str], info: SearchInfo):
    col = Listing.attrs[d.key]
    low, high = _num(args.get(f"a_{d.key}_min", "")), _num(args.get(f"a_{d.key}_max", ""))
    unit = d.unit or ("meses" if d.type == "age" else "")
    if low is not None:
        q = q.filter(col.as_float() >= low)
        info.chips.append((f"{d.label} desde {low:g} {unit}".strip(), [f"a_{d.key}_min"]))
    if high is not None:
        q = q.filter(col.as_float() <= high)
        info.chips.append((f"{d.label} hasta {high:g} {unit}".strip(), [f"a_{d.key}_max"]))
    return q


def _apply_exact(q, d: AttributeDef, args: Mapping[str, str], info: SearchInfo):
    col = Listing.attrs[d.key]
    value = (args.get(f"a_{d.key}") or "").strip()
    if not value:
        return q
    if d.type == "bool":
        if value in ("si", "no"):
            q = q.filter(col.as_boolean().is_(value == "si"))
            info.chips.append((f"{d.label}: {'Sí' if value == 'si' else 'No'}", [f"a_{d.key}"]))
    elif d.type == "choice":
        q = q.filter(col.as_string() == value)
        info.chips.append((f"{d.label}: {value}", [f"a_{d.key}"]))
    else:
        q = q.filter(func.lower(col.as_string()).contains(value.lower()))
        info.chips.append((f"{d.label}: {value}", [f"a_{d.key}"]))
    return q


def _apply_near(q, args: Mapping[str, str], info: SearchInfo):
    near = parse_near(args)
    if not near:
        return q
    center, radius = near
    info.near, info.radius = center, radius
    info.chips.append((f"Cerca de mí ({radius} km)", ["near", "radio"]))
    return q.filter(Listing.id.in_(listing_ids_near(center, radius)))


def _apply_attributes(q, args: Mapping[str, str], info: SearchInfo):
    info.defs = filterable_defs(info.sub or info.root)
    for d in info.defs:
        if d.type in ("int", "decimal", "age"):
            q = _apply_range(q, d, args, info)
        else:
            q = _apply_exact(q, d, args, info)
    return q


def search(args: Mapping[str, str]) -> tuple[Any, SearchInfo]:
    """Interpreta los filtros del listado público. Devuelve (query ordenada, info para la plantilla)."""
    info = SearchInfo()
    q = Listing.public_query()
    q = _apply_category(q, args, info)
    q = _apply_text(q, args, info)
    if args.get("tipo") in AD_TYPES:
        q = q.filter(Listing.ad_type == args["tipo"])
        info.chips.append((AD_TYPES[args["tipo"]], ["tipo"]))
    q = _apply_place(q, args, info)
    q = _apply_near(q, args, info)
    q = _apply_price(q, args, info)
    q = _apply_attributes(q, args, info)
    info.order = args.get("orden") if args.get("orden") in SORTS else "recientes"
    return q.order_by(SORTS[info.order][1](), Listing.id.desc()), info

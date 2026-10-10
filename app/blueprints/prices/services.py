"""Armado de las pantallas de precios de referencia."""

from dataclasses import dataclass

from ...models import Category, Municipality
from ...services import prices as price_service
from ...services.prices import PriceRow, PriceSummary, Trend


@dataclass
class PriceIndex:
    roots: list[Category]
    selected: Category | None
    rows: list[PriceRow]


def price_index(root_slug: str | None) -> PriceIndex:
    price_service.refresh_if_stale()
    selected = Category.root_by_slug(root_slug) if root_slug else None
    return PriceIndex(Category.active_roots(), selected, price_service.latest_rows(selected))


@dataclass
class PriceDetail:
    category: Category
    unit: str
    rows: list[PriceRow]
    trend: Trend


def price_detail(slug: str, unit: str | None) -> PriceDetail | None:
    price_service.refresh_if_stale()
    category = Category.sub_by_slug(slug)
    if not category:
        return None
    rows = [r for r in price_service.latest_rows(category.root) if r.category.id == category.id]
    if not rows:
        return PriceDetail(category, unit or "", [], Trend([], [], [], []))
    chosen = next((r for r in rows if r.unit == unit), rows[0])
    return PriceDetail(category, chosen.unit, rows, price_service.trend(category, chosen.unit))


def reference_for_form(category_id: str, unit: str, municipality_id: str) -> tuple[PriceSummary | None, str]:
    """Precio de referencia para mostrar mientras se publica. (None, 'region') si faltan datos."""
    category = Category.query.get(int(category_id)) if category_id.isdigit() else None
    if not category or not unit:
        return None, "region"
    municipality = Municipality.query.get(int(municipality_id)) if municipality_id.isdigit() else None
    return price_service.live_reference(category, unit, municipality.id if municipality else None)

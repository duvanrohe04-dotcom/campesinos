"""Precios de referencia por subcategoría y unidad, con descarte de valores atípicos (regla del rango intercuartil)."""

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy.exc import IntegrityError

from ..constants import (
    AD_BUY,
    PRICE_BY_AGREEMENT,
    PRICE_MIN_SAMPLE,
    PRICE_OUTLIER_IQR,
    PRICE_TREND_WEEKS,
    PRICE_WINDOW_DAYS,
    PUBLIC_STATUSES,
)
from ..extensions import db
from ..models import Category, Listing, PriceSnapshot
from ..utils import utcnow


@dataclass(frozen=True)
class PriceSummary:
    average: int
    median: int
    minimum: int
    maximum: int
    sample_size: int
    discarded: int = 0


def remove_outliers(prices: list[int]) -> list[int]:
    """Quita valores fuera de [Q1 - 1.5·IQR, Q3 + 1.5·IQR]. Con menos de 4 datos no se descarta nada."""
    if len(prices) < 4:
        return list(prices)
    q1, _, q3 = statistics.quantiles(prices, n=4, method="inclusive")
    spread = (q3 - q1) * PRICE_OUTLIER_IQR
    low, high = q1 - spread, q3 + spread
    return [p for p in prices if low <= p <= high]


def summarize(prices: list[int], min_sample: int = PRICE_MIN_SAMPLE) -> PriceSummary | None:
    """Promedio, mediana, mínimo y máximo sin atípicos. None si no hay suficientes datos para ser confiable."""
    kept = remove_outliers(sorted(prices))
    if len(kept) < min_sample:
        return None
    return PriceSummary(
        average=round(statistics.fmean(kept)),
        median=round(statistics.median(kept)),
        minimum=min(kept),
        maximum=max(kept),
        sample_size=len(kept),
        discarded=len(prices) - len(kept),
    )


def _price_rows(
    category_id: int | None = None,
    unit: str | None = None,
    municipality_id: int | None = None,
    as_of: datetime | None = None,
):
    """Precios de los anuncios de la ventana de 30 días que termina en `as_of` (por defecto, ahora)."""
    cutoff = (as_of or utcnow()) - timedelta(days=PRICE_WINDOW_DAYS)
    query = db.session.query(Listing.category_id, Listing.price_unit, Listing.price).filter(
        Listing.price.isnot(None),
        Listing.price > 0,
        Listing.ad_type != AD_BUY,
        Listing.status.in_(PUBLIC_STATUSES),
        Listing.price_unit.isnot(None),
        Listing.price_unit != PRICE_BY_AGREEMENT,
        Listing.created_at >= cutoff,
    )
    if as_of:
        query = query.filter(Listing.created_at <= as_of)
    if category_id:
        query = query.filter(Listing.category_id == category_id)
    if unit:
        query = query.filter(Listing.price_unit == unit)
    if municipality_id:
        query = query.filter(Listing.municipality_id == municipality_id)
    return query.all()


def live_reference(
    category: Category, unit: str, municipality_id: int | None = None
) -> tuple[PriceSummary | None, str]:
    """Precio de referencia en el momento. Intenta con el municipio y, si hay pocos datos, usa toda la región.
    Devuelve (resumen, alcance) con alcance 'municipio' o 'region'."""
    if municipality_id:
        local = summarize([p for _, _, p in _price_rows(category.id, unit, municipality_id)])
        if local:
            return local, "municipio"
    return summarize([p for _, _, p in _price_rows(category.id, unit)]), "region"


def update_snapshots(today: date | None = None) -> int:
    """Calcula y guarda (o actualiza) el precio de referencia de un día (por defecto hoy) para cada subcategoría
    y unidad, con los anuncios de los 30 días anteriores a ese día. Devuelve cuántos."""
    today = today or utcnow().date()
    as_of = None if today >= utcnow().date() else datetime.combine(today, time.max)
    grouped: dict[tuple[int, str], list[int]] = defaultdict(list)
    for category_id, unit, price in _price_rows(as_of=as_of):
        grouped[(category_id, unit)].append(int(price))
    saved = 0
    for (category_id, unit), prices in grouped.items():
        summary = summarize(prices)
        if not summary:
            continue
        snapshot = PriceSnapshot.query.filter_by(category_id=category_id, unit=unit, day=today).first()
        snapshot = snapshot or PriceSnapshot(category_id=category_id, unit=unit, day=today)
        snapshot.average, snapshot.median = summary.average, summary.median
        snapshot.minimum, snapshot.maximum, snapshot.sample_size = summary.minimum, summary.maximum, summary.sample_size
        db.session.add(snapshot)
        saved += 1
    db.session.commit()
    return saved


def backfill_snapshots(weeks: int = PRICE_TREND_WEEKS) -> int:
    """Reconstruye el histórico semanal con los anuncios que ya existen (útil al cargar datos de ejemplo
    o al activar la función con anuncios previos). Devuelve cuántos precios guardó."""
    today = utcnow().date()
    saved = update_snapshots(today)
    for week in range(1, weeks + 1):
        saved += update_snapshots(today - timedelta(weeks=week))
    return saved


def refresh_if_stale() -> bool:
    """Calcula los precios de hoy si todavía no se han calculado (así la página funciona aunque no corra el cron).
    Devuelve True si hizo el cálculo."""
    today = utcnow().date()
    latest = db.session.query(db.func.max(PriceSnapshot.day)).scalar()
    if latest and latest >= today:
        return False
    try:
        update_snapshots(today)
    except IntegrityError:  # otra petición lo calculó al mismo tiempo
        db.session.rollback()
    return True


@dataclass
class PriceRow:
    category: Category
    unit: str
    snapshot: PriceSnapshot
    change_percent: float | None  # frente a hace ~4 semanas


def _change(snapshot: PriceSnapshot) -> float | None:
    past = (
        PriceSnapshot.query.filter(
            PriceSnapshot.category_id == snapshot.category_id,
            PriceSnapshot.unit == snapshot.unit,
            PriceSnapshot.day <= snapshot.day - timedelta(days=21),
        )
        .order_by(PriceSnapshot.day.desc())
        .first()
    )
    if not past or not past.average:
        return None
    return round((snapshot.average - past.average) / past.average * 100, 1)


def latest_rows(root: Category | None = None) -> list[PriceRow]:
    """Último precio de cada subcategoría/unidad (opcionalmente de una sola categoría)."""
    latest_day = db.session.query(db.func.max(PriceSnapshot.day)).scalar()
    if not latest_day:
        return []
    query = PriceSnapshot.query.filter(PriceSnapshot.day >= latest_day - timedelta(days=2))
    if root:
        query = query.filter(PriceSnapshot.category_id.in_(root.family_ids))
    newest: dict[tuple[int, str], PriceSnapshot] = {}
    for snapshot in query.order_by(PriceSnapshot.day.asc()).all():
        newest[(snapshot.category_id, snapshot.unit)] = snapshot
    rows = [PriceRow(s.category, s.unit, s, _change(s)) for s in newest.values()]
    return sorted(rows, key=lambda r: (r.category.root.position, r.category.position, r.unit))


@dataclass
class Trend:
    labels: list[str]
    averages: list[int]
    minimums: list[int]
    maximums: list[int]


def trend(category: Category, unit: str, weeks: int = PRICE_TREND_WEEKS) -> Trend:
    """Promedio semanal de las últimas `weeks` semanas (a partir del histórico)."""
    since = utcnow().date() - timedelta(weeks=weeks)
    snapshots = (
        PriceSnapshot.query.filter(
            PriceSnapshot.category_id == category.id, PriceSnapshot.unit == unit, PriceSnapshot.day >= since
        )
        .order_by(PriceSnapshot.day.asc())
        .all()
    )
    by_week: dict[date, list[PriceSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        by_week[snapshot.day - timedelta(days=snapshot.day.weekday())].append(snapshot)
    weeks_sorted = sorted(by_week)
    return Trend(
        labels=[w.strftime("%d/%m") for w in weeks_sorted],
        averages=[round(statistics.fmean(s.average for s in by_week[w])) for w in weeks_sorted],
        minimums=[min(s.minimum for s in by_week[w]) for w in weeks_sorted],
        maximums=[max(s.maximum for s in by_week[w]) for w in weeks_sorted],
    )

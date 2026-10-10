"""Ubicación aproximada: redondeo de coordenadas, distancias y filtro «cerca de mí»."""

import math
from collections.abc import Mapping

from sqlalchemy import func

from ..constants import (
    COLOMBIA_BOUNDS,
    COORDINATE_DECIMALS,
    EARTH_RADIUS_KM,
    NEAR_DEFAULT_RADIUS,
    NEAR_MAX_CANDIDATES,
    NEAR_RADIUS_OPTIONS,
    STATUS_ACTIVE,
)
from ..extensions import db
from ..models import Listing, Municipality, Village

Point = tuple[float, float]


def in_colombia(lat: float, lng: float) -> bool:
    lat_min, lat_max, lng_min, lng_max = COLOMBIA_BOUNDS
    return lat_min <= lat <= lat_max and lng_min <= lng <= lng_max


def round_point(lat: float, lng: float) -> Point:
    """Redondea a ~1 km para no exponer la ubicación exacta de una finca."""
    return round(lat, COORDINATE_DECIMALS), round(lng, COORDINATE_DECIMALS)


def parse_point(raw_lat: str | None, raw_lng: str | None) -> Point | None:
    """Convierte texto en un punto redondeado. None si vienen vacíos; ValueError si son inválidos."""
    raw_lat, raw_lng = (raw_lat or "").strip(), (raw_lng or "").strip()
    if not raw_lat and not raw_lng:
        return None
    try:
        lat, lng = float(raw_lat.replace(",", ".")), float(raw_lng.replace(",", "."))
    except ValueError:
        raise ValueError("El punto del mapa no es válido. Vuelve a marcarlo.") from None
    if not (math.isfinite(lat) and math.isfinite(lng)) or not in_colombia(lat, lng):
        raise ValueError("El punto debe estar en Colombia.")
    return round_point(lat, lng)


def haversine_km(a: Point, b: Point) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def bounding_box(center: Point, radius_km: float) -> tuple[float, float, float, float]:
    """(lat_min, lat_max, lng_min, lng_max) que contiene el círculo."""
    lat, lng = center
    dlat = math.degrees(radius_km / EARTH_RADIUS_KM)
    dlng = math.degrees(radius_km / (EARTH_RADIUS_KM * max(math.cos(math.radians(lat)), 0.01)))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def listing_point(listing: Listing) -> tuple[Point | None, bool]:
    """Punto de un anuncio y si es el que marcó el vendedor (True) o el centro de la vereda/municipio (False)."""
    if listing.lat is not None and listing.lng is not None:
        return (listing.lat, listing.lng), True
    village = listing.village
    if village and village.lat is not None and village.lng is not None:
        return (village.lat, village.lng), False
    municipality = listing.municipality
    if municipality and municipality.lat is not None and municipality.lng is not None:
        return (municipality.lat, municipality.lng), False
    return None, False


def parse_near(args: Mapping[str, str]) -> tuple[Point, int] | None:
    """Lee ?near=lat,lng&radio=10 de la URL. None si no hay o no son válidos."""
    raw = args.get("near") or ""
    if "," not in raw:
        return None
    lat_raw, _, lng_raw = raw.partition(",")
    try:
        point = parse_point(lat_raw, lng_raw)
    except ValueError:
        return None
    if not point:
        return None
    try:
        radius = int(args.get("radio", NEAR_DEFAULT_RADIUS))
    except ValueError:
        radius = NEAR_DEFAULT_RADIUS
    return point, radius if radius in NEAR_RADIUS_OPTIONS else NEAR_DEFAULT_RADIUS


def listing_ids_near(center: Point, radius_km: float) -> list[int]:
    """Ids de anuncios activos a menos de `radius_km`. Usa el punto del anuncio o, si no tiene, el de la
    vereda o el municipio. Filtra primero por un cuadro (consulta SQL) y afina con la distancia real."""
    lat_min, lat_max, lng_min, lng_max = bounding_box(center, radius_km)
    lat = func.coalesce(Listing.lat, Village.lat, Municipality.lat)
    lng = func.coalesce(Listing.lng, Village.lng, Municipality.lng)
    rows = (
        db.session.query(Listing.id, lat, lng)
        .outerjoin(Village, Village.id == Listing.village_id)
        .join(Municipality, Municipality.id == Listing.municipality_id)
        .filter(Listing.status == STATUS_ACTIVE, lat.between(lat_min, lat_max), lng.between(lng_min, lng_max))
        .limit(NEAR_MAX_CANDIDATES)
        .all()
    )
    return [lid for lid, plat, plng in rows if haversine_km(center, (plat, plng)) <= radius_km]

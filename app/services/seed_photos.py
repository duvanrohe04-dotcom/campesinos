"""Fotos reales de demostración para los anuncios de ejemplo.

Las fotos están en `seeds/photos/` (descargadas de Wikimedia Commons con licencias libres: CC0, dominio público,
CC BY y CC BY-SA). El autor y la licencia de cada una están en `seeds/photos/credits.json` y se muestran bajo la
galería del anuncio. Solo se usan en desarrollo; los anuncios reales llevan fotos de sus dueños.
"""

import json
import pathlib

from flask import current_app

from ..constants import AD_BUY
from ..extensions import db
from ..models import Listing, ListingImage
from . import images

PHOTOS_DIR = pathlib.Path(__file__).resolve().parents[2] / "seeds" / "photos"

# subcategoría (slug) → fotos candidatas (se rotan para dar algo de variedad)
PHOTOS_BY_SUBCATEGORY: dict[str, list[str]] = {
    "frutas": ["guayaba"], "cafe": ["cafe"], "platano-y-banano": ["platano"], "yuca-y-tuberculos": ["yuca"],
    "maiz-y-granos": ["maiz"], "hortalizas": ["tomate"], "cana": ["cana"], "otros-cultivos": ["semillas"],
    "vacas": ["vaca_holstein", "vaca_criolla"], "toros": ["toro"], "novillos": ["novillo"], "terneros": ["ternero"],
    "vacas-paridas": ["vaca_criolla"], "caballos": ["caballo"], "yeguas": ["yegua"], "mulas": ["mula"],
    "burros": ["burro"], "potros": ["yegua"], "cerdos-de-engorde": ["cerdo"], "lechones": ["lechon"],
    "cerdas-de-cria": ["cerdo"], "reproductores": ["cerdo"], "gallinas-ponedoras": ["ponedoras"],
    "pollos-de-engorde": ["pollos_engorde"], "gallinas-criollas": ["gallina_criolla"], "pollitos": ["pollitos"],
    "patos": ["pato"], "cabras": ["cabra"], "conejos": ["conejo"], "peces": ["pez"], "abejas": ["colmena"],
    "leche": ["leche"], "queso-y-cuajada": ["queso"], "huevos": ["huevos"], "miel": ["miel"],
    "bocadillo": ["bocadillo"], "panela": ["panela"], "conservas": ["bocadillo"], "arepas-y-masas": ["arepas"],
    "artesanias": ["artesania"], "semillas": ["semillas"], "plantulas": ["plantulas"], "concentrado": ["concentrado"],
    "pasto-de-corte": ["pasto"], "guadanas": ["guadana"], "fumigadoras": ["fumigadora"], "trapiches": ["trapiche"],
    "motobombas": ["motobomba"], "jornaleros": ["jornaleros"], "ordeno": ["ordeno"], "fumigacion": ["fumigadora"],
    "veterinario": ["veterinario"], "transporte": ["camion"], "herreria": ["herreria"],
    "alquiler-de-potreros": ["potrero"],
}  # fmt: skip


def _credit_text(info: dict) -> str:
    return f"Foto: {info['author']} · {info['license']} · Wikimedia Commons"[:300]


def seed_photos() -> int:
    """Pone una foto real a cada anuncio de ejemplo que no tiene (excepto los de «Compro/Busco»).
    Cada anuncio recibe su propia copia del archivo. Devuelve cuántos anuncios recibieron foto."""
    credits_file = PHOTOS_DIR / "credits.json"
    if not credits_file.exists():
        current_app.logger.warning("No hay fotos de demostración en %s", PHOTOS_DIR)
        return 0
    credits = json.loads(credits_file.read_text(encoding="utf-8"))
    counters: dict[str, int] = {}
    done = 0
    for listing in Listing.query.filter(Listing.ad_type != AD_BUY).order_by(Listing.id).all():
        if listing.images:
            continue
        options = PHOTOS_BY_SUBCATEGORY.get(listing.category.slug)
        if not options:
            continue
        index = counters.get(listing.category.slug, 0)
        counters[listing.category.slug] = index + 1
        name = options[index % len(options)]
        source = PHOTOS_DIR / f"{name}.jpg"
        if not source.exists() or name not in credits:
            continue
        filename = images.save_from_path(str(source))
        listing.images.append(
            ListingImage(
                filename=filename, position=0, credit=_credit_text(credits[name]),
                credit_url=credits[name].get("source"),
            )  # fmt: skip
        )
        done += 1
    db.session.commit()
    return done

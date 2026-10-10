"""Datos personales de la cuenta (Ley 1581 de 2012): descargar lo que guardamos y eliminar la cuenta."""

import secrets
from typing import Any

from sqlalchemy import update

from ..extensions import db
from ..models import (
    Article,
    ContactMessage,
    Favorite,
    Listing,
    Notification,
    Rating,
    Report,
    User,
    VerificationCode,
)
from ..utils import utcnow
from . import images

DELETED_NAME = "Usuario eliminado"


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def export_user_data(user: User) -> dict[str, Any]:
    """Todo lo que la plataforma guarda de la persona, en un diccionario listo para descargar como JSON."""
    return {
        "generado_en": _iso(utcnow()),
        "cuenta": {
            "nombre": user.name,
            "celular": user.phone,
            "correo": user.email,
            "correo_verificado": user.email_verified,
            "finca": user.farm_name,
            "descripcion": user.bio,
            "municipio": user.municipality.name if user.municipality else None,
            "vereda": user.village.name if user.village else user.village_other,
            "creada_en": _iso(user.created_at),
            "terminos_aceptados_en": _iso(user.terms_accepted_at),
            "version_de_terminos": user.terms_version,
        },
        "anuncios": [
            {
                "id": listing.id,
                "titulo": listing.title,
                "descripcion": listing.description,
                "tipo": listing.ad_type,
                "categoria": listing.category.name,
                "precio": listing.price,
                "unidad_de_precio": listing.price_unit,
                "cantidad": listing.quantity,
                "estado": listing.status,
                "datos_especificos": listing.attrs,
                "publicado_en": _iso(listing.created_at),
                "vence_en": _iso(listing.expires_at),
            }
            for listing in Listing.query.filter_by(user_id=user.id).order_by(Listing.created_at)
        ],
        "favoritos": [
            favorite.listing.title
            for favorite in Favorite.query.filter_by(user_id=user.id).order_by(Favorite.created_at)
        ],
        "busquedas_guardadas": [{"nombre": s.name, "filtros": s.filters} for s in user.saved_searches],
        "calificaciones_recibidas": [
            {"estrellas": r.stars, "comentario": r.comment, "fecha": _iso(r.created_at)}
            for r in Rating.query.filter_by(seller_id=user.id)
        ],
        "calificaciones_dadas": [
            {"a": r.seller.farm_name or r.seller.name, "estrellas": r.stars, "comentario": r.comment}
            for r in Rating.query.filter_by(rater_id=user.id)
        ],
        "mensajes_de_contacto": [
            {"asunto": m.subject, "mensaje": m.message, "fecha": _iso(m.created_at)}
            for m in ContactMessage.query.filter_by(user_id=user.id)
        ],
    }


def delete_account(user: User) -> None:
    """Borra lo que se puede borrar y anonimiza la cuenta.

    La fila del usuario se conserva anonimizada porque otras cosas apuntan a ella (calificaciones que la persona dio,
    reportes). Sin nombre, celular, correo, foto ni anuncios, ya no identifica a nadie."""
    for listing in Listing.query.filter_by(user_id=user.id):
        for image in listing.images:
            images.delete_files(image.filename)
        db.session.delete(listing)  # su cascada borra favoritos, estadísticas, reportes y avisos del anuncio
    if user.photo:
        images.delete_files(user.photo)

    Favorite.query.filter_by(user_id=user.id).delete()
    Notification.query.filter_by(user_id=user.id).delete()
    VerificationCode.query.filter_by(user_id=user.id).delete()
    ContactMessage.query.filter_by(user_id=user.id).delete()
    Rating.query.filter_by(seller_id=user.id).delete()  # lo que opinaron de esta persona se va con ella
    for search in user.saved_searches.all():
        db.session.delete(search)
    db.session.execute(update(Report).where(Report.reporter_id == user.id).values(reporter_id=None))
    db.session.execute(update(Article).where(Article.author_id == user.id).values(author_id=None))

    user.name = DELETED_NAME
    user.phone = f"0{user.id:09d}"  # 10 dígitos que empiezan por 0: ningún celular real, y es único por cuenta
    user.email = user.email_verified_at = user.farm_name = user.bio = user.photo = None
    user.village_id = user.village_other = user.municipality_id = None
    user.set_password(secrets.token_hex(32))  # nadie conoce esta clave: la cuenta no se puede abrir
    user.is_enabled = False
    user.is_verified_seller = False
    user.deleted_at = utcnow()
    db.session.commit()

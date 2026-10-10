"""Calificaciones de vendedores y resumen de reputación."""

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ..constants import RATING_COMMENT_MAX, RATING_HIDDEN, RATING_MAX, RATING_MIN, RATING_VISIBLE, STATUS_SOLD
from ..extensions import db
from ..models import Listing, Rating, User


class RatingError(ValueError):
    """Error con mensaje en español para mostrar al usuario."""


@dataclass
class SellerReputation:
    average: float | None
    count: int
    sold: int
    member_since: str


def reputation(seller: User) -> SellerReputation:
    average, count = (
        db.session.query(func.avg(Rating.stars), func.count(Rating.id))
        .filter(Rating.seller_id == seller.id, Rating.status == RATING_VISIBLE)
        .one()
    )
    sold = Listing.query.filter_by(user_id=seller.id, status=STATUS_SOLD).count()
    return SellerReputation(
        average=round(float(average), 1) if average is not None else None,
        count=count,
        sold=sold,
        member_since=seller.created_at.strftime("%m/%Y"),
    )


def visible_reviews(seller: User, limit: int = 20) -> list[Rating]:
    return (
        Rating.query.options(joinedload(Rating.rater))
        .filter_by(seller_id=seller.id, status=RATING_VISIBLE)
        .order_by(Rating.created_at.desc())
        .limit(limit)
        .all()
    )


def own_rating(seller: User, rater: User) -> Rating | None:
    return Rating.query.filter_by(seller_id=seller.id, rater_id=rater.id).first()


def rate_seller(seller: User, rater: User, stars: int, comment: str | None) -> Rating:
    """Crea o actualiza la calificación de `rater` a `seller` (una por pareja)."""
    if seller.id == rater.id:
        raise RatingError("No puedes calificarte a ti mismo.")
    if seller.is_admin or not seller.is_enabled:
        raise RatingError("Este vendedor no se puede calificar.")
    if not RATING_MIN <= stars <= RATING_MAX:
        raise RatingError("Elige de 1 a 5 estrellas.")
    comment = (comment or "").strip()[:RATING_COMMENT_MAX] or None
    rating = own_rating(seller, rater) or Rating(seller_id=seller.id, rater_id=rater.id)
    rating.stars, rating.comment = stars, comment
    db.session.add(rating)
    db.session.commit()
    return rating


def set_visibility(rating: Rating, visible: bool) -> None:
    rating.status = RATING_VISIBLE if visible else RATING_HIDDEN
    db.session.commit()


def list_for_moderation(status: str = RATING_VISIBLE, limit: int = 100) -> list[Rating]:
    return (
        Rating.query.options(joinedload(Rating.seller), joinedload(Rating.rater))
        .filter_by(status=status)
        .order_by(Rating.created_at.desc())
        .limit(limit)
        .all()
    )

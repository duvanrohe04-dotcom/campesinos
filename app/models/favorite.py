from __future__ import annotations

from ..extensions import db
from ..utils import utcnow


class Favorite(db.Model):
    __tablename__ = "favorites"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

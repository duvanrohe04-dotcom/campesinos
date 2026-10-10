from __future__ import annotations

from ..extensions import db
from ..utils import utcnow
from .category import JSONType


class SavedSearch(db.Model):
    """Búsqueda guardada: los filtros del listado con un nombre. Genera avisos cuando aparecen anuncios nuevos."""

    __tablename__ = "saved_searches"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    filters = db.Column(JSONType, nullable=False, default=dict)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_checked_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("saved_searches", lazy="dynamic", cascade="all, delete"))


class Notification(db.Model):
    """Aviso dentro de la app (centro de notificaciones)."""

    __tablename__ = "notifications"
    __table_args__ = (
        db.UniqueConstraint("user_id", "kind", "listing_id", "saved_search_id", name="uq_notification_once"),
        db.Index("ix_notifications_unread", "user_id", "read_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kind = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(300))
    url = db.Column(db.String(300))
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"))
    saved_search_id = db.Column(db.Integer, db.ForeignKey("saved_searches.id"))
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    user = db.relationship("User")
    # Al borrar el anuncio o la búsqueda guardada, sus avisos se borran con ellos (en PostgreSQL, si no, da error 500)
    listing = db.relationship("Listing", backref=db.backref("notifications", cascade="all, delete-orphan"))
    saved_search = db.relationship("SavedSearch", backref=db.backref("notifications", cascade="all, delete-orphan"))

    @property
    def is_unread(self) -> bool:
        return self.read_at is None

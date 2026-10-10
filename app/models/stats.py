from __future__ import annotations

from ..extensions import db


class DailyStat(db.Model):
    """Vistas y contactos de un anuncio por día (para el gráfico semanal del panel)."""

    __tablename__ = "daily_stats"

    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), primary_key=True)
    day = db.Column(db.Date, primary_key=True)
    views = db.Column(db.Integer, nullable=False, default=0)
    whatsapp = db.Column(db.Integer, nullable=False, default=0)
    calls = db.Column(db.Integer, nullable=False, default=0)

    listing = db.relationship("Listing", backref=db.backref("daily_stats", cascade="all, delete-orphan"))

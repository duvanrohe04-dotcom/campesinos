from __future__ import annotations

from ..extensions import db


class PriceSnapshot(db.Model):
    """Precio de referencia de una subcategoría y unidad en un día (histórico para la tendencia)."""

    __tablename__ = "price_snapshots"
    __table_args__ = (db.UniqueConstraint("category_id", "unit", "day", name="uq_price_snapshot"),)

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    unit = db.Column(db.String(30), nullable=False)
    day = db.Column(db.Date, nullable=False, index=True)
    average = db.Column(db.BigInteger, nullable=False)
    median = db.Column(db.BigInteger, nullable=False)
    minimum = db.Column(db.BigInteger, nullable=False)
    maximum = db.Column(db.BigInteger, nullable=False)
    sample_size = db.Column(db.Integer, nullable=False)

    category = db.relationship("Category")

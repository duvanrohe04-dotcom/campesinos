from __future__ import annotations

from datetime import timedelta

from flask import current_app
from sqlalchemy.orm import joinedload, selectinload

from ..constants import STATUS_ACTIVE, VILLAGE_OTHER_MAX
from ..extensions import db
from ..utils import place_text, slugify, utcnow
from .category import JSONType


class Listing(db.Model):
    __tablename__ = "listings"
    __table_args__ = (
        db.Index("ix_listings_browse", "status", "category_id", "created_at"),
        db.Index("ix_listings_place", "municipality_id", "status"),
        db.Index("ix_listings_coords", "lat", "lng"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    ad_type = db.Column(db.String(10), nullable=False, default="vendo")
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.BigInteger, index=True)  # COP enteros
    price_unit = db.Column(db.String(30))
    negotiable = db.Column(db.Boolean, nullable=False, default=False)
    quantity = db.Column(db.Integer)
    available_from = db.Column(db.Date)
    municipality_id = db.Column(db.Integer, db.ForeignKey("municipalities.id"), nullable=False)
    village_id = db.Column(db.Integer, db.ForeignKey("villages.id"))
    village_other = db.Column(db.String(VILLAGE_OTHER_MAX))  # vereda escrita a mano cuando no está en la lista
    lat = db.Column(db.Float)  # ubicación aproximada (redondeada a ~1 km)
    lng = db.Column(db.Float)
    attrs = db.Column(JSONType, nullable=False, default=dict)
    status = db.Column(db.String(10), nullable=False, default=STATUS_ACTIVE, index=True)
    expires_at = db.Column(db.DateTime, index=True)
    renewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    views_count = db.Column(db.Integer, nullable=False, default=0)
    whatsapp_clicks = db.Column(db.Integer, nullable=False, default=0)
    call_clicks = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("User", backref=db.backref("listings", lazy="dynamic"))
    category = db.relationship("Category")
    municipality = db.relationship("Municipality")
    village = db.relationship("Village")
    images = db.relationship(
        "ListingImage", backref="listing", order_by="ListingImage.position", cascade="all, delete-orphan"
    )
    favorites = db.relationship("Favorite", backref="listing", cascade="all, delete-orphan")
    reports = db.relationship("Report", backref="listing", cascade="all, delete-orphan")

    # --- Consultas reutilizables (evitan repetir eager loading) ---
    @classmethod
    def card_query(cls):
        """Consulta con todo lo que necesita una tarjeta de publicación (evita N+1)."""
        return cls.query.options(
            selectinload(cls.images),
            joinedload(cls.municipality),
            joinedload(cls.village),
            joinedload(cls.category),
            joinedload(cls.user),
        )

    @classmethod
    def public_query(cls):
        """Anuncios activos listos para mostrarse."""
        return cls.card_query().filter(cls.status == STATUS_ACTIVE)

    # --- Ciclo de vida ---
    def set_expiry(self) -> None:
        self.expires_at = utcnow() + timedelta(days=current_app.config["LISTING_DURATION_DAYS"])

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    @property
    def main_image(self) -> ListingImage | None:
        return self.images[0] if self.images else None

    @property
    def slug(self) -> str:
        return slugify(f"{self.title} {self.municipality.name if self.municipality else ''}")

    @property
    def location_text(self) -> str:
        return place_text(
            self.village.name if self.village else None,
            self.village_other,
            self.municipality.name if self.municipality else None,
        )

    @property
    def days_left(self) -> int | None:
        return (self.expires_at - utcnow()).days if self.expires_at else None

    @property
    def expiring_soon(self) -> bool:
        days = self.days_left
        return self.is_active and days is not None and days <= current_app.config["EXPIRING_SOON_DAYS"]

    @property
    def contacts_count(self) -> int:
        return (self.whatsapp_clicks or 0) + (self.call_clicks or 0)

    def __repr__(self) -> str:
        return f"<Listing {self.id} {self.title}>"


class ListingImage(db.Model):
    __tablename__ = "listing_images"

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False, index=True)
    filename = db.Column(db.String(80), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    credit = db.Column(db.String(300))  # «Autor · Licencia» de fotos de bancos libres (demostración)
    credit_url = db.Column(db.String(300))

    @property
    def thumb(self) -> str:
        return self.filename.replace(".webp", "_t.webp")

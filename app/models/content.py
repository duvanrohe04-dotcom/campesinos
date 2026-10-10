from __future__ import annotations

from ..extensions import db
from ..utils import slugify, utcnow


class Event(db.Model):
    """Evento de la agenda: ferias, subastas, mercados, jornadas de vacunación, capacitaciones."""

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="otro")
    description = db.Column(db.Text)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)  # hora local de Colombia
    ends_at = db.Column(db.DateTime)
    place = db.Column(db.String(160))
    municipality_id = db.Column(db.Integer, db.ForeignKey("municipalities.id"))
    organizer = db.Column(db.String(120))  # SENA, ICA, alcaldía…
    image = db.Column(db.String(80))
    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    municipality = db.relationship("Municipality")

    @property
    def slug(self) -> str:
        return slugify(self.title)

    @property
    def image_thumb(self) -> str | None:
        return self.image.replace(".webp", "_t.webp") if self.image else None

    @property
    def last_day(self):
        return (self.ends_at or self.starts_at).date()


class Article(db.Model):
    """Artículo de «Consejos del campo». El HTML del cuerpo se guarda ya sanitizado."""

    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    summary = db.Column(db.String(300), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(20), nullable=False, index=True)
    cover = db.Column(db.String(80))
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reading_minutes = db.Column(db.Integer, nullable=False, default=1)
    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    published_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    author = db.relationship("User")

    @property
    def cover_thumb(self) -> str | None:
        return self.cover.replace(".webp", "_t.webp") if self.cover else None

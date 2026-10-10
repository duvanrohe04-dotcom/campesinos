from __future__ import annotations

from sqlalchemy.dialects.postgresql import JSONB

from ..constants import DEFAULT_PRICE_UNITS
from ..extensions import db

# JSONB en PostgreSQL, JSON en SQLite
JSONType = db.JSON().with_variant(JSONB(), "postgresql")


class Category(db.Model):
    """Categoría (parent_id NULL) o subcategoría (con parent_id). Dos niveles."""

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), index=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    icon = db.Column(db.String(30), nullable=False, default="campo")
    position = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    requires_ica = db.Column(db.Boolean, nullable=False, default=False)
    home_section = db.Column(db.String(20))  # 'animales' | 'mesa' | None
    price_units = db.Column(JSONType, nullable=False, default=list)

    children = db.relationship(
        "Category",
        backref=db.backref("parent", remote_side=[id], lazy="joined"),
        order_by="Category.position, Category.name",
    )

    # --- Consultas reutilizables ---
    @classmethod
    def active_roots(cls) -> list[Category]:
        return cls.query.filter_by(parent_id=None, is_active=True).order_by(cls.position).all()

    @classmethod
    def all_roots(cls) -> list[Category]:
        return cls.query.filter_by(parent_id=None).order_by(cls.position).all()

    @classmethod
    def root_by_slug(cls, slug: str) -> Category | None:
        return cls.query.filter_by(slug=slug, parent_id=None).first()

    @classmethod
    def sub_by_slug(cls, slug: str) -> Category | None:
        return cls.query.filter(cls.slug == slug, cls.parent_id.isnot(None)).first()

    # --- Propiedades ---
    @property
    def root(self) -> Category:
        return self.parent or self

    @property
    def family_ids(self) -> list[int]:
        """Id de la categoría y de todas sus subcategorías."""
        return [self.id, *(c.id for c in self.children)]

    @property
    def units(self) -> list[str]:
        return self.root.price_units or DEFAULT_PRICE_UNITS

    @property
    def needs_ica(self) -> bool:
        return bool(self.root.requires_ica)

    @property
    def active_children(self) -> list[Category]:
        return [c for c in self.children if c.is_active]

    def __repr__(self) -> str:
        return f"<Category {self.slug}>"


class AttributeDef(db.Model):
    """Definición de un atributo específico. Se asocia a una categoría raíz y la heredan sus subcategorías."""

    __tablename__ = "attribute_defs"
    __table_args__ = (db.UniqueConstraint("category_id", "key", name="uq_attr_category_key"),)

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    key = db.Column(db.String(40), nullable=False)
    label = db.Column(db.String(80), nullable=False)
    type = db.Column(db.String(10), nullable=False, default="text")
    required = db.Column(db.Boolean, nullable=False, default=False)
    choices = db.Column(JSONType)  # lista de opciones para type='choice'
    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    unit = db.Column(db.String(20))
    help_text = db.Column(db.String(160))
    is_filterable = db.Column(db.Boolean, nullable=False, default=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    category = db.relationship(
        "Category", backref=db.backref("attribute_defs", order_by="AttributeDef.position", cascade="all, delete-orphan")
    )

    def __repr__(self) -> str:
        return f"<AttributeDef {self.key}>"

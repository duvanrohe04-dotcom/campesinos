from __future__ import annotations

from ..extensions import db


class Municipality(db.Model):
    __tablename__ = "municipalities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    department = db.Column(db.String(60), nullable=False, default="Santander")
    lat = db.Column(db.Float)  # centro aproximado del municipio
    lng = db.Column(db.Float)

    villages = db.relationship("Village", backref="municipality", order_by="Village.name", cascade="all, delete-orphan")

    @classmethod
    def ordered(cls) -> list[Municipality]:
        return cls.query.order_by(cls.name).all()

    def __repr__(self) -> str:
        return f"<Municipality {self.name}>"


class Village(db.Model):
    __tablename__ = "villages"

    id = db.Column(db.Integer, primary_key=True)
    municipality_id = db.Column(db.Integer, db.ForeignKey("municipalities.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    lat = db.Column(db.Float)  # centro aproximado de la vereda (opcional)
    lng = db.Column(db.Float)

    @classmethod
    def ordered(cls) -> list[Village]:
        return cls.query.order_by(cls.name).all()

    def __repr__(self) -> str:
        return f"<Village {self.name}>"

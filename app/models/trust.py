from __future__ import annotations

from ..constants import PURPOSE_VERIFY_EMAIL, RATING_VISIBLE
from ..extensions import db
from ..utils import utcnow


class VerificationCode(db.Model):
    """Código de un solo uso enviado por correo (se guarda solo el hash; vence y limita intentos).

    `purpose` distingue verificar el correo de recuperar la contraseña."""

    __tablename__ = "verification_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    purpose = db.Column(db.String(20), nullable=False, default=PURPOSE_VERIFY_EMAIL)
    code_hash = db.Column(db.String(64), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Rating(db.Model):
    """Calificación (1-5) y comentario a un vendedor. Una por usuario y vendedor."""

    __tablename__ = "ratings"
    __table_args__ = (db.UniqueConstraint("seller_id", "rater_id", name="uq_rating_seller_rater"),)

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    rater_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    stars = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(300))
    status = db.Column(db.String(10), nullable=False, default=RATING_VISIBLE, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    seller = db.relationship("User", foreign_keys=[seller_id])
    rater = db.relationship("User", foreign_keys=[rater_id])

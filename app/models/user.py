from __future__ import annotations

from datetime import timedelta

from flask import current_app
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..constants import EMAIL_MAX, ROLE_ADMIN, ROLE_SELLER, VILLAGE_OTHER_MAX
from ..extensions import db, login_manager
from ..utils import place_text, utcnow


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(10), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False, default=ROLE_SELLER)
    municipality_id = db.Column(db.Integer, db.ForeignKey("municipalities.id"), index=True)
    village_id = db.Column(db.Integer, db.ForeignKey("villages.id"))
    village_other = db.Column(db.String(VILLAGE_OTHER_MAX))  # vereda escrita a mano cuando no está en la lista
    farm_name = db.Column(db.String(120))
    bio = db.Column(db.String(500))
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    failed_logins = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    terms_accepted_at = db.Column(db.DateTime)  # Ley 1581: fecha de aceptación
    terms_version = db.Column(db.String(20))
    photo = db.Column(db.String(80))  # archivo .webp en uploads (miniatura *_t.webp)
    phone_verified_at = db.Column(
        db.DateTime
    )  # en desuso: el celular ya no se verifica por código (ver email_verified_at)
    email = db.Column(db.String(EMAIL_MAX), unique=True, index=True)  # opcional; permite recuperar la clave
    email_verified_at = db.Column(db.DateTime)  # el correo se confirmó con un código
    deleted_at = db.Column(db.DateTime)  # la persona eliminó su cuenta: los datos personales se borraron (Ley 1581)
    is_verified_seller = db.Column(db.Boolean, nullable=False, default=False)  # insignia otorgada por el admin

    municipality = db.relationship("Municipality")
    village = db.relationship("Village")

    # --- Consultas ---
    @classmethod
    def by_phone(cls, phone: str | None) -> User | None:
        return cls.query.filter_by(phone=phone).first() if phone else None

    @classmethod
    def by_email(cls, email: str | None) -> User | None:
        return cls.query.filter_by(email=email).first() if email else None

    # --- Flask-Login ---
    @property
    def is_active(self) -> bool:
        return self.is_enabled

    # --- Roles ---
    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def can_sell(self) -> bool:
        """Todos los usuarios registrados pueden publicar cualquier tipo de anuncio (vender, comprar, alquilar)."""
        return self.is_enabled

    # --- Contraseña y bloqueo de intentos ---
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > utcnow())

    def register_failure(self) -> None:
        self.failed_logins = (self.failed_logins or 0) + 1
        if self.failed_logins >= current_app.config["MAX_LOGIN_ATTEMPTS"]:
            self.locked_until = utcnow() + timedelta(minutes=current_app.config["LOCKOUT_MINUTES"])
            self.failed_logins = 0

    def register_success(self) -> None:
        self.failed_logins = 0
        self.locked_until = None

    @property
    def photo_thumb(self) -> str | None:
        return self.photo.replace(".webp", "_t.webp") if self.photo else None

    @property
    def email_verified(self) -> bool:
        return bool(self.email) and self.email_verified_at is not None

    @property
    def location_text(self) -> str:
        return place_text(
            self.village.name if self.village else None,
            self.village_other,
            self.municipality.name if self.municipality else None,
        )

    def __repr__(self) -> str:
        return f"<User {self.phone}>"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))

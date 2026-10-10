from __future__ import annotations

from ..constants import MESSAGE_NEW
from ..extensions import db
from ..utils import utcnow


class ContactMessage(db.Model):
    """Mensaje del formulario de contacto; lo lee el admin."""

    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(120), nullable=False)  # celular o correo
    subject = db.Column(db.String(20), nullable=False, default="otro")
    message = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    status = db.Column(db.String(10), nullable=False, default=MESSAGE_NEW, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")

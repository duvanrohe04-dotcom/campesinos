"""Entrega de notificaciones.

Siempre se guarda un aviso dentro de la app (centro de notificaciones). Además, cada canal listado en
NOTIFICATION_CHANNELS recibe el aviso: WhatsApp y correo están **preparados detrás de esta interfaz** pero aún no
integrados (solo registran en el log). Para integrarlos, implementa `send` en la clase correspondiente.
"""

from typing import Protocol

from flask import current_app

from ..extensions import db
from ..models import Notification, User
from ..utils import utcnow


class Channel(Protocol):
    def send(self, notification: Notification) -> None: ...


class InAppChannel:
    """El aviso ya queda guardado en la base de datos; no hay nada más que enviar."""

    def send(self, notification: Notification) -> None:
        return None


class WhatsAppChannel:
    """Pendiente de integración (Cloud API de Meta)."""

    def send(self, notification: Notification) -> None:
        current_app.logger.info("[whatsapp:pendiente] a usuario %s: %s", notification.user_id, notification.title)


class EmailChannel:
    """Pendiente de integración."""

    def send(self, notification: Notification) -> None:
        current_app.logger.info("[correo:pendiente] a usuario %s: %s", notification.user_id, notification.title)


CHANNELS: dict[str, type[Channel]] = {"in_app": InAppChannel, "whatsapp": WhatsAppChannel, "email": EmailChannel}


def notify(
    user: User,
    kind: str,
    title: str,
    body: str | None = None,
    url: str | None = None,
    listing_id: int | None = None,
    saved_search_id: int | None = None,
) -> Notification | None:
    """Crea el aviso (una sola vez por usuario/tipo/anuncio/búsqueda) y lo envía por los canales configurados."""
    exists = Notification.query.filter_by(
        user_id=user.id, kind=kind, listing_id=listing_id, saved_search_id=saved_search_id
    ).first()
    if exists:
        return None
    notification = Notification(
        user_id=user.id,
        kind=kind,
        title=title[:160],
        body=(body or "")[:300] or None,
        url=url,
        listing_id=listing_id,
        saved_search_id=saved_search_id,
    )
    db.session.add(notification)
    db.session.commit()
    for name in current_app.config.get("NOTIFICATION_CHANNELS", ["in_app"]):
        channel = CHANNELS.get(name)
        if channel:
            channel().send(notification)
    return notification


def unread_count(user: User) -> int:
    return Notification.query.filter_by(user_id=user.id, read_at=None).count()


def list_for(user: User, limit: int = 50) -> list[Notification]:
    return Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(limit).all()


def mark_read(notification: Notification) -> None:
    if notification.is_unread:
        notification.read_at = utcnow()
        db.session.commit()


def mark_all_read(user: User) -> None:
    Notification.query.filter_by(user_id=user.id, read_at=None).update({"read_at": utcnow()})
    db.session.commit()

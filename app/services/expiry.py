"""Vencimiento y renovación de publicaciones."""

from ..constants import STATUS_ACTIVE, STATUS_EXPIRED
from ..extensions import db
from ..models import Listing
from ..utils import utcnow


def expire_listings() -> int:
    """Marca como vencidas las publicaciones activas pasadas de fecha. Devuelve cuántas fueron."""
    count = Listing.query.filter(Listing.status == STATUS_ACTIVE, Listing.expires_at < utcnow()).update(
        {"status": STATUS_EXPIRED}, synchronize_session=False
    )
    db.session.commit()
    return count


def renew(listing: Listing) -> None:
    """Reinicia el plazo de 30 días y reactiva el anuncio (no hace commit)."""
    listing.set_expiry()
    listing.renewed_at = utcnow()
    listing.status = STATUS_ACTIVE

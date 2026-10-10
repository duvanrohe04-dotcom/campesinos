from __future__ import annotations

from ..constants import REPORT_OPEN
from ..extensions import db
from ..utils import utcnow


class Report(db.Model):
    """Reporte de una publicación (fraude, animal enfermo, información falsa)."""

    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False, index=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reason = db.Column(db.String(20), nullable=False)
    detail = db.Column(db.String(500))
    status = db.Column(db.String(10), nullable=False, default=REPORT_OPEN, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    reporter = db.relationship("User")

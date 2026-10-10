from wtforms import RadioField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from ...constants import REPORT_DETAIL_MAX, REPORT_REASONS
from ...forms import BaseForm


class ReportForm(BaseForm):
    reason = RadioField(
        "¿Qué pasa con este anuncio?",
        choices=list(REPORT_REASONS.items()),
        validators=[DataRequired("Elige el motivo del reporte.")],
    )
    detail = TextAreaField("Cuéntanos más (opcional)", validators=[Optional(), Length(max=REPORT_DETAIL_MAX)])

from wtforms import HiddenField
from wtforms.validators import Length

from ...forms import BaseForm


class SaveSearchForm(BaseForm):
    """Guarda los filtros actuales del listado (llegan como query string en un campo oculto)."""

    query = HiddenField(validators=[Length(max=1000)])

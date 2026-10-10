"""Vereda elegida de la lista o escrita a mano («Otra vereda»)."""

from ..constants import VILLAGE_OTHER_ID, VILLAGE_OTHER_MAX
from ..extensions import db
from ..models import Village

MSG_VILLAGE_OTHER_REQUIRED = "Escribe el nombre de tu vereda."
MSG_VILLAGE_WRONG_MUNICIPALITY = "Esa vereda no es de ese municipio."


def resolve_village(
    village_id: int | None, other: str | None, municipality_id: int | None
) -> tuple[Village | None, str | None, tuple[str, str] | None]:
    """Devuelve (vereda, vereda_escrita, error). El error es (campo, mensaje) o None.

    - Sin vereda: (None, None, None).
    - Vereda de la lista: se valida que sea del municipio; el texto escrito se descarta.
    - «Otra vereda» (id 0): el nombre escrito es obligatorio.
    """
    if village_id == VILLAGE_OTHER_ID:
        name = " ".join((other or "").split())[:VILLAGE_OTHER_MAX]
        if not name:
            return None, None, ("village_other", MSG_VILLAGE_OTHER_REQUIRED)
        return None, name, None
    if not village_id:
        return None, None, None
    village = db.session.get(Village, village_id)
    if not village or village.municipality_id != municipality_id:
        return None, None, ("village_id", MSG_VILLAGE_WRONG_MUNICIPALITY)
    return village, None, None

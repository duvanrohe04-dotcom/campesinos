"""Formulario de publicar/editar: un bloque de opciones por categoría, sin ids repetidos ni valores marcados en bloques ocultos."""

import re
from collections import Counter

from app.models import Listing, User

from ..conftest import login


def _blocks(html: str) -> list[tuple[bool, str]]:
    """[(deshabilitado, html)] de cada <fieldset data-root=…> del formulario."""
    out = []
    for part in re.split(r'(?=<fieldset[^>]*data-root=")', html)[1:]:
        tag = re.match(r"<fieldset[^>]*>", part).group(0)
        out.append(("disabled" in tag, part.split("</fieldset>")[0]))
    return out


def _checked_radios(html: str) -> list[tuple[str, bool]]:
    """[(nombre, en_bloque_deshabilitado)] de los radios de unidad de precio y datos de categoría que vienen marcados."""
    found = []
    for disabled, block in _blocks(html):
        for tag in re.findall(r"<input[^>]*type=\"radio\"[^>]*>", block):
            name = re.search(r'name="(price_unit|attr_\w+)"', tag)
            if name and " checked" in tag:
                found.append((name.group(1), disabled))
    return found


def test_edit_form_marks_options_only_in_the_listings_own_category(client):
    login(client, "3000000000", "admin12345")  # el admin puede editar cualquier anuncio
    problems = []
    for listing in Listing.query.filter_by(status="active").all():
        html = client.get(f"/panel/anuncio/{listing.id}/editar").get_data(as_text=True)
        marked = _checked_radios(html)
        counts = Counter(name for name, _ in marked)
        problems += [f"{listing.id}: {name} marcado {n} veces" for name, n in counts.items() if n > 1]
        problems += [
            f"{listing.id}: {name} marcado en un bloque deshabilitado" for name, disabled in marked if disabled
        ]
    assert not problems, problems[:5]


def test_edit_form_has_no_repeated_ids(client):
    login(client, "3000000000", "admin12345")
    listing = Listing.query.filter(Listing.user.has(User.phone == "3101112233")).first()
    for path in (f"/panel/anuncio/{listing.id}/editar", "/publicar"):
        html = client.get(path).get_data(as_text=True)
        repeated = [i for i, n in Counter(re.findall(r'\sid="([^"]+)"', html)).items() if n > 1]
        assert not repeated, (path, repeated[:5])


def test_each_label_points_to_a_field_inside_its_own_block(client):
    """Antes, «Raza» de una categoría apuntaba al campo «Raza» de otra (oculta): tocar la etiqueta no enfocaba nada."""
    login(client, "3101112233")
    html = client.get("/publicar").get_data(as_text=True)
    for _disabled, block in _blocks(html):
        for target in re.findall(r'<label[^>]*for="(f-[^"]+)"', block):
            assert f'id="{target}"' in block, target


def test_edited_agricultural_listing_keeps_its_price_unit(client):
    """Antes se perdía la unidad de precio al guardar y salía «Elige cómo cobras»."""
    login(client, "3101112233")
    listing = Listing.query.filter(Listing.user.has(User.phone == "3101112233")).first()
    html = client.get(f"/panel/anuncio/{listing.id}/editar").get_data(as_text=True)
    unit_marks = [(n, d) for n, d in _checked_radios(html) if n == "price_unit"]
    assert unit_marks == [("price_unit", False)]


def test_calendar_days_with_events_are_tappable_links(client):
    html = client.get("/agenda").get_data(as_text=True)
    assert re.search(
        r'<a href="[^"]+" class="block -m-1 p-1 min-h-\[2\.75rem\][^"]*"\s+aria-label="\d+: \d+ eventos?\.', html
    )
    assert 'class="hidden sm:block truncate' in html  # los títulos solo aparecen en pantallas más anchas


def test_touch_friendly_css_is_compiled(client):
    css = client.get("/static/css/app.css").get_data(as_text=True)
    assert ".leaflet-container .leaflet-bar a" in css and "44px" in css
    assert "footer ul a" in css

"""Opciones «Otra»: vereda escrita a mano y opciones de lista que piden escribir cuál. Teléfono visible."""

from app.models import Category, Listing, Municipality, User
from app.services.attributes import display_attrs
from app.services.places import resolve_village

from ..conftest import url_of
from .test_auth import REGISTER
from .test_listing_crud import TITLE, created, form_data


def _velez_id() -> int:
    return Municipality.query.filter_by(slug="velez").first().id


def test_resolve_village_cases(app):
    mun = _velez_id()
    assert resolve_village(None, "ignorada", mun) == (None, None, None)
    assert resolve_village(0, "  La   Esperanza ", mun) == (None, "La Esperanza", None)
    assert resolve_village(0, "  ", mun)[2][0] == "village_other"
    assert resolve_village(999999, None, mun)[2][0] == "village_id"


def test_register_with_other_village(client):
    client.post("/registro", data={**REGISTER, "village_id": "0", "village_other": "Vereda Nueva"})
    assert User.by_phone("3159998877").village_other == "Vereda Nueva"


def test_register_other_village_requires_name(client):
    html = client.post("/registro", data={**REGISTER, "village_id": "0", "village_other": ""}).get_data(as_text=True)
    assert "Escribe el nombre de tu vereda." in html
    assert User.by_phone("3159998877") is None


def test_listing_with_other_village_shows_name(seller):
    data = form_data(village_id="0", village_other="El Mirador")
    assert seller.post("/publicar", data=data).status_code == 302
    listing = created()
    assert listing.village is None and listing.village_other == "El Mirador"
    assert listing.location_text.startswith("El Mirador,")


def test_listing_other_village_without_name_is_rejected(seller):
    response = seller.post("/publicar", data=form_data(village_id="0", village_other=""))
    assert response.status_code == 200 and "Escribe el nombre de tu vereda." in response.get_data(as_text=True)
    assert Listing.query.filter_by(title=TITLE).first() is None


def _bird_data(**overrides):
    sub = Category.sub_by_slug("gallinas-ponedoras")
    data = {
        "ad_type": "vendo", "category_id": sub.id, "title": "Gallinas de otra raza",
        "attr_raza": "Otra", "attr_edad_semanas": "30", "attr_en_produccion": "si",
        "quantity": "10", "price": "28.000", "price_unit": "unidad", "municipality_id": _velez_id(),
    }  # fmt: skip
    return {**data, **overrides}


def test_choice_other_stores_and_shows_written_text(seller):
    response = seller.post("/publicar", data=_bird_data(attr_raza__other="Rhode Island"))
    assert response.status_code == 302
    listing = Listing.query.filter_by(title="Gallinas de otra raza").one()
    assert listing.attrs["raza"] == "Otra" and listing.attrs["raza__other"] == "Rhode Island"
    assert ("Raza", "Otra: Rhode Island") in display_attrs(listing)
    assert "Otra: Rhode Island" in seller.get(url_of(listing)).get_data(as_text=True)


def test_choice_other_requires_text(seller):
    html = seller.post("/publicar", data=_bird_data()).get_data(as_text=True)
    assert "Escribe cuál es." in html


def test_other_text_is_dropped_for_regular_choice(seller):
    seller.post("/publicar", data=_bird_data(attr_raza="Criolla", attr_raza__other="basura"))
    listing = Listing.query.filter_by(title="Gallinas de otra raza").one()
    assert "raza__other" not in listing.attrs


def test_publish_form_renders_other_fields(seller):
    html = seller.get("/publicar").get_data(as_text=True)
    assert "data-village-other" in html and 'name="village_other"' in html
    assert 'name="attr_raza__other"' in html


def test_phone_is_masked_on_listing_and_profile_and_revealed_on_tap(client):
    listing = Listing.query.first()
    phone = listing.user.phone
    pretty = f"{phone[:3]} {phone[3:6]} {phone[6:]}"
    masked = f"{phone[:3]} ••• ••{phone[-2:]}"
    for page in (client.get(url_of(listing)), client.get(f"/vendedor/{listing.user.id}")):
        html = page.get_data(as_text=True)
        assert masked in html and "Ver celular" in html
        assert phone not in html and pretty not in html and f"tel:+57{phone}" not in html
    assert pretty in client.get(f"/anuncio/{listing.id}/contacto").get_data(as_text=True)
    assert pretty in client.get(f"/vendedor/{listing.user.id}/contacto").get_data(as_text=True)

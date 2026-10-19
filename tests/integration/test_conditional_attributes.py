"""Datos condicionales: «¿Preñada?» solo se pregunta, se guarda y se muestra si el animal es Hembra."""

import re
from types import SimpleNamespace

import pytest

from app.extensions import db
from app.models import AttributeDef, Category, Listing, Municipality
from app.services.attributes import display_attrs, form_values_from_attrs, is_shown, validate_attrs

from ..conftest import url_of
from .test_listing_crud import TITLE, created, form_data


def prenada_def() -> AttributeDef:
    """«Preñada» de bovinos (equinos y porcinos tienen la suya)."""
    return AttributeDef.query.filter(AttributeDef.key == "prenada", AttributeDef.category.has(slug="bovinos")).one()


def test_prenada_is_defined_as_female_only(app):
    d = prenada_def()
    assert (d.show_if_key, d.show_if_values) == ("sexo", ["Hembra"])


@pytest.mark.parametrize(
    ("value", "expected"),
    [("Hembra", True), ("Macho", False), ("", False), (None, False), ("hembra", False)],
)
def test_is_shown_depends_on_the_other_answer(app, value, expected):
    assert is_shown(prenada_def(), lambda key: value) is expected


def test_is_shown_always_true_without_a_condition(app):
    assert is_shown(AttributeDef.query.filter_by(key="raza").first(), lambda key: None) is True


def test_boolean_answers_are_compared_as_si_no(app):
    d = SimpleNamespace(show_if_key="vacunacion", show_if_values=["si"])
    assert is_shown(d, lambda key: True) and not is_shown(d, lambda key: False)
    assert is_shown(d, lambda key: "si") and not is_shown(d, lambda key: "no")


def test_validation_ignores_prenada_for_males_even_if_it_arrives(app):
    category = Category.sub_by_slug("novillos")
    form = {"attr_sexo": "Macho", "attr_raza": "Cebú", "attr_prenada": "si", "attr_edad": "18", "attr_peso": "300"}
    clean, errors = validate_attrs(category, form)
    assert not errors and "prenada" not in clean and clean["sexo"] == "Macho"


def test_validation_keeps_prenada_for_females(app):
    category = Category.sub_by_slug("vacas")
    form = {"attr_sexo": "Hembra", "attr_raza": "Holstein", "attr_prenada": "si", "attr_edad": "30", "attr_peso": "400"}
    clean, errors = validate_attrs(category, form)
    assert not errors and clean["prenada"] is True


def test_a_required_conditional_attribute_is_not_demanded_when_it_does_not_apply(app):
    d = prenada_def()
    d.required = True
    db.session.commit()
    category = Category.sub_by_slug("terneros")  # pregunta el sexo (los Novillos ya lo traen fijo)
    _, errors = validate_attrs(
        category, {"attr_sexo": "Macho", "attr_raza": "Cebú", "attr_edad": "18", "attr_peso": "9"}
    )
    assert "attr_prenada" not in errors
    _, errors = validate_attrs(
        category, {"attr_sexo": "Hembra", "attr_raza": "Cebú", "attr_edad": "18", "attr_peso": "9"}
    )
    assert errors["attr_prenada"] == "Este dato es obligatorio."


def test_publishing_a_male_never_stores_prenada(seller):
    seller.post("/publicar", data=form_data(attr_prenada="si"))
    assert "prenada" not in created().attrs


def test_publishing_a_female_stores_prenada(seller):
    data = form_data(category_id=Category.sub_by_slug("vacas").id, attr_sexo="Hembra", attr_prenada="si")
    seller.post("/publicar", data=data)
    assert created().attrs["prenada"] is True


def test_changing_sex_to_male_on_edit_drops_prenada(seller):
    # «Terneros» pregunta el sexo; en «Vacas» no se puede cambiar porque el tipo ya lo decide
    data = form_data(category_id=Category.sub_by_slug("terneros").id, attr_sexo="Hembra", attr_prenada="si")
    seller.post("/publicar", data=data)
    listing = created()
    assert listing.attrs["prenada"] is True
    seller.post(f"/panel/anuncio/{listing.id}/editar", data={**data, "attr_sexo": "Macho"})
    assert "prenada" not in created().attrs


def test_detail_hides_a_stale_prenada_answer_for_males(client):
    listing = Listing.query.filter(Listing.category.has(slug="novillos")).first()
    listing.attrs = {**listing.attrs, "sexo": "Macho", "prenada": False}  # dato viejo guardado antes de la regla
    db.session.commit()
    labels = [label for label, _ in display_attrs(listing)]
    assert "Preñada" not in labels and "Sexo" in labels
    assert "Preñada" not in client.get(url_of(listing)).get_data(as_text=True)
    assert "attr_prenada" not in form_values_from_attrs(listing.category, listing.attrs)


def test_detail_shows_prenada_for_females(seller):
    data = form_data(category_id=Category.sub_by_slug("vacas").id, attr_sexo="Hembra", attr_prenada="si")
    seller.post("/publicar", data=data)
    listing = created()
    assert ("Preñada", "Sí") in display_attrs(listing)
    assert "Preñada" in seller.get(url_of(listing)).get_data(as_text=True)


def test_publish_form_renders_prenada_inside_a_conditional_block(seller):
    html = seller.get("/publicar").get_data(as_text=True)
    blocks = re.findall(r'<div data-show-if="attr_sexo" data-show-values="([^"]*)"([^>]*)>', html)
    assert blocks, "falta el bloque condicional de «Preñada»"
    values, attrs = blocks[0]
    assert "Hembra" in values and "hidden" in attrs  # nuevo anuncio: sin sexo elegido, oculto


def _prenada_block(html: str) -> str:
    """Etiqueta de apertura del bloque de «Preñada» del formulario (el de la categoría elegida, no el de otras)."""
    blocks = re.findall(r'<div data-show-if="attr_sexo"[^>]*>', html)
    # el formulario trae un bloque por categoría; el de bovinos es el que no está dentro de un fieldset deshabilitado
    active = re.search(
        r'<fieldset[^>]*data-root="\d+"(?![^>]*disabled)[^>]*>\s*(?:(?!</fieldset>).)*?(<div data-show-if="attr_sexo"[^>]*>)',
        html,
        re.S,
    )
    return active.group(1) if active else blocks[0]


def test_edit_form_shows_prenada_block_only_for_females(seller):
    male_data = form_data(attr_prenada="si")
    seller.post("/publicar", data=male_data)
    male = created()
    html = seller.get(f"/panel/anuncio/{male.id}/editar").get_data(as_text=True)
    assert "hidden" in _prenada_block(html)  # macho: «Preñada» oculta

    female_data = form_data(category_id=Category.sub_by_slug("vacas").id, attr_sexo="Hembra", attr_prenada="si")
    female_data["title"] = "Vaca de prueba preñada"
    seller.post("/publicar", data=female_data)
    female = Listing.query.filter_by(title="Vaca de prueba preñada").one()
    html = seller.get(f"/panel/anuncio/{female.id}/editar").get_data(as_text=True)
    assert "hidden" not in _prenada_block(html)  # hembra: «Preñada» visible


def test_admin_can_define_a_conditional_question(admin):
    category = Category.root_by_slug("equinos")
    data = {"label": "Capado", "type": "bool", "show_if_key": "tipo", "show_if_values": "Caballo"}
    response = admin.post(f"/admin/categorias/{category.id}/atributos/nuevo", data=data, follow_redirects=True)
    assert response.status_code == 200
    created_def = AttributeDef.query.filter_by(category_id=category.id, key="capado").one()
    assert (created_def.show_if_key, created_def.show_if_values) == ("tipo", ["Caballo"])


@pytest.mark.parametrize(
    ("show_key", "show_values", "message"),
    [
        ("tipo", "Elefante", "no es una opción"),
        ("tipo", "", "Escribe cuándo se pregunta"),
        ("inventado", "x", "Elige uno"),
    ],
)
def test_admin_rejects_a_wrong_condition(admin, show_key, show_values, message):
    category = Category.root_by_slug("equinos")
    data = {"label": "Otro dato", "type": "bool", "show_if_key": show_key, "show_if_values": show_values}
    response = admin.post(f"/admin/categorias/{category.id}/atributos/nuevo", data=data)
    assert message in response.get_data(as_text=True)
    assert not AttributeDef.query.filter_by(category_id=category.id, label="Otro dato").count()


def test_admin_edit_form_shows_the_saved_condition(admin):
    d = prenada_def()
    html = admin.get(f"/admin/atributos/{d.id}/editar").get_data(as_text=True)
    assert "Pregunta condicional" in html and 'value="Hembra"' in html
    assert re.search(r'<option[^>]*value="sexo"[^>]*selected|<option selected[^>]*value="sexo"', html)


def test_conditional_script_is_served(client):
    script = client.get("/static/js/app.js").get_data(as_text=True)
    assert "syncConditionalFields" in script and "data-show-if" in script


def test_municipality_fixture_still_available(app):  # form_data() de test_listing_crud la necesita
    assert Municipality.query.filter_by(slug="velez").first() and TITLE

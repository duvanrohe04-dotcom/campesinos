"""Reglas del formulario: datos que decide el tipo, preguntas encadenadas y «a convenir» sin precio."""

import re

import pytest

from app.models import AttributeDef, Category, Listing
from app.services.attributes import display_attrs, validate_attrs

from .test_listing_crud import created, form_data

BASE = {"attr_raza": "Cebú", "attr_edad": "18", "attr_peso": "300"}


def radio_for(slug: str) -> str:
    """Expresión que encuentra el radio de ese tipo en el formulario de publicar."""
    return rf'<input type="radio" name="category_id" value="{Category.sub_by_slug(slug).id}"[^>]*>'


def validate(slug: str, **answers):
    return validate_attrs(Category.sub_by_slug(slug), {**BASE, **{f"attr_{k}": v for k, v in answers.items()}})


# ---------- Datos que decide el tipo ----------
@pytest.mark.parametrize(
    ("slug", "key", "value"),
    [
        ("toros", "sexo", "Macho"), ("novillos", "sexo", "Macho"), ("vacas", "sexo", "Hembra"),
        ("vacas-paridas", "sexo", "Hembra"), ("cerdas-de-cria", "sexo", "Hembra"),
        ("caballos", "tipo", "Caballo"), ("yeguas", "tipo", "Yegua"), ("mulas", "tipo", "Mula"), ("burros", "tipo", "Burro"),
    ],
)  # fmt: skip
def test_the_type_decides_the_answer_even_if_the_form_says_otherwise(app, slug, key, value):
    clean, errors = validate_attrs(Category.sub_by_slug(slug), {f"attr_{key}": "Otro valor", "attr_edad": "12"})
    assert f"attr_{key}" not in errors and clean[key] == value


def test_the_fixed_answer_satisfies_a_required_question_left_empty(app):
    clean, errors = validate("toros")  # sin enviar «sexo», que es obligatorio
    assert not errors and clean["sexo"] == "Macho"


def test_types_without_a_fixed_answer_still_ask(app):
    _, errors = validate_attrs(Category.sub_by_slug("terneros"), {})
    assert "attr_sexo" in errors


def test_publishing_a_bull_as_female_stores_male(seller):
    seller.post("/publicar", data=form_data(category_id=Category.sub_by_slug("toros").id, attr_sexo="Hembra"))
    assert created().attrs["sexo"] == "Macho"


def test_a_mare_gets_the_pregnancy_question_and_a_horse_does_not(app):
    clean, _ = validate_attrs(Category.sub_by_slug("yeguas"), {"attr_prenada": "si"})
    assert clean["tipo"] == "Yegua" and clean["prenada"] is True
    clean, _ = validate_attrs(Category.sub_by_slug("caballos"), {"attr_prenada": "si"})
    assert clean["tipo"] == "Caballo" and "prenada" not in clean


def test_only_sows_get_the_pregnancy_question_in_pigs(app):
    clean, _ = validate_attrs(Category.sub_by_slug("cerdas-de-cria"), {"attr_prenada": "si"})
    assert clean["prenada"] is True
    clean, _ = validate_attrs(Category.sub_by_slug("reproductores"), {"attr_sexo": "Macho", "attr_prenada": "si"})
    assert "prenada" not in clean


# ---------- Preguntas encadenadas ----------
def test_gestation_months_only_when_pregnant(app):
    clean, errors = validate("vacas", prenada="si", meses_gestacion="7")
    assert not errors and clean["meses_gestacion"] == 7
    clean, _ = validate("vacas", prenada="no", meses_gestacion="7")
    assert "meses_gestacion" not in clean


def test_chain_is_cut_when_the_first_question_does_not_apply(app):
    """Macho: no se pregunta «Preñada», y por tanto tampoco los meses de gestación, aunque lleguen en el formulario."""
    clean, errors = validate("terneros", sexo="Macho", prenada="si", meses_gestacion="7")
    assert not errors and "prenada" not in clean and "meses_gestacion" not in clean


def test_gestation_months_have_a_sane_range(app):
    _, errors = validate("vacas", prenada="si", meses_gestacion="12")
    assert "máximo 9" in errors["attr_meses_gestacion"]


def test_milk_liters_only_for_milk_purposes(app):
    clean, errors = validate("vacas", proposito="Leche", litros_dia="14,5")
    assert not errors and clean["litros_dia"] == 14.5
    clean, _ = validate("vacas", proposito="Carne", litros_dia="14")
    assert "litros_dia" not in clean
    _, errors = validate("vacas", proposito="Doble propósito", litros_dia="500")
    assert "máximo 80" in errors["attr_litros_dia"]


def test_detail_hides_chained_answers_that_no_longer_apply(app):
    listing = Listing.query.filter(Listing.category.has(slug="novillos")).first()
    listing.attrs = {
        **listing.attrs,
        "sexo": "Macho",
        "prenada": True,
        "meses_gestacion": 5,
    }  # dato viejo inconsistente
    labels = [label for label, _ in display_attrs(listing)]
    assert "Preñada" not in labels and "Meses de gestación" not in labels


# ---------- Precio ----------
def test_by_agreement_never_stores_a_price(seller):
    data = form_data(
        category_id=Category.sub_by_slug("veterinario").id, price_unit="a convenir", price="500.000", attr_zona="Vélez"
    )
    seller.post("/publicar", data=data)
    listing = created()
    assert listing.price is None and listing.price_unit == "a convenir"


def test_a_real_price_is_still_stored(seller):
    seller.post("/publicar", data=form_data())
    assert created().price == 3200000


# ---------- Pantalla ----------
def test_publish_form_declares_the_rules_for_the_script(seller):
    html = seller.get("/publicar").get_data(as_text=True)
    assert 'id="price-fields"' in html
    assert 'data-attr="attr_sexo"' in html
    toros = re.search(radio_for("toros"), html)
    assert toros and "data-fixed=" in toros.group(0) and "Macho" in toros.group(0)
    terneros = re.search(radio_for("terneros"), html)
    assert terneros and "data-fixed=" in terneros.group(0) and "Macho" not in terneros.group(0)


def test_scripts_apply_the_rules(client):
    app_js = client.get("/static/js/app.js").get_data(as_text=True)
    publish_js = client.get("/static/js/publish.js").get_data(as_text=True)
    assert "syncFixedFields" in app_js and "data-fixed" in app_js and "syncRules" in app_js
    assert "syncPrice" in publish_js and "price-fields" in publish_js


# ---------- Coherencia de los datos del seed ----------
def test_every_fixed_answer_points_to_a_real_option(app):
    from app.services.attributes import defs_for

    for sub in (c for c in Category.query if c.fixed_attrs):  # JSON: None se guarda como «null», no como NULL de SQL
        assert sub.parent_id, f"{sub.name}: los datos fijos van en subcategorías"
        by_key = {d.key: d for d in defs_for(sub)}
        for key, value in sub.fixed_attrs.items():
            assert key in by_key, f"{sub.name}: no existe el dato «{key}»"
            assert by_key[key].type == "choice" and value in by_key[key].choices, f"{sub.name}: «{value}» no es opción"


def test_every_condition_points_to_an_earlier_real_question_with_valid_values(app):
    for d in (a for a in AttributeDef.query if a.show_if_key):
        siblings = {s.key: s for s in AttributeDef.query.filter_by(category_id=d.category_id)}
        controlling = siblings.get(d.show_if_key)
        assert controlling, f"{d.category.slug}.{d.key} depende de «{d.show_if_key}», que no existe"
        assert (
            controlling.position < d.position
        ), f"{d.key} debe ir después de «{d.show_if_key}» para que la cadena funcione"
        allowed = controlling.choices if controlling.type == "choice" else ["si", "no"]
        assert controlling.type in ("choice", "bool")
        assert d.show_if_values and set(d.show_if_values) <= set(allowed), f"{d.key}: valores fuera de las opciones"

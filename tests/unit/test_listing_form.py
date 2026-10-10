from datetime import date

import pytest
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Category, Listing, Municipality, User, Village
from app.services.listing_form import (
    apply_images,
    parse_listing_form,
    step_for_error,
    values_from_listing,
)

from ..conftest import png_bytes


def base_form(**overrides):
    data = {
        "ad_type": "vendo",
        "category_id": str(Category.sub_by_slug("novillos").id),
        "title": "Novillo cebú de prueba",
        "attr_sexo": "Macho",
        "price": "3.200.000",
        "price_unit": "cabeza",
        "municipality_id": str(Municipality.query.filter_by(slug="velez").one().id),
    }
    data.update(overrides)
    return data


def parse(**overrides):
    return parse_listing_form(base_form(**overrides), User.by_phone("3101112233"))


def test_valid_form_returns_clean_data(app):
    data, errors = parse(quantity="3", description="Sano", negotiable="1", available_from="2026-12-01")
    assert not errors
    assert data["price"] == 3200000 and data["quantity"] == 3 and data["negotiable"] is True
    assert data["available_from"] == date(2026, 12, 1) and data["attrs"] == {"sexo": "Macho"}


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"ad_type": "otro"}, "ad_type"),
        ({"category_id": ""}, "category_id"),
        ({"category_id": "99999"}, "category_id"),
        ({"title": "abc"}, "title"),
        ({"title": "x" * 81}, "title"),
        ({"description": "x" * 1001}, "description"),
        ({"quantity": "cero"}, "quantity"),
        ({"quantity": "0"}, "quantity"),
        ({"price": "gratis"}, "price"),
        ({"price": "99999999999"}, "price"),
        ({"price_unit": "galón"}, "price_unit"),
        ({"available_from": "mañana"}, "available_from"),
        ({"municipality_id": ""}, "municipality_id"),
    ],
)
def test_each_invalid_field_reports_its_error(app, overrides, field):
    _, errors = parse(**overrides)
    assert field in errors


def test_root_category_with_children_requires_subcategory(app):
    _, errors = parse(category_id=str(Category.root_by_slug("bovinos").id))
    assert "tipo exacto" in errors["category_id"]


def test_price_optional_for_wanted_ads_and_by_agreement(app):
    assert "price" not in parse(ad_type="compro", price="")[1]
    assert "price" in parse(price="")[1]
    services = Category.sub_by_slug("veterinario")
    _, errors = parse_listing_form(
        base_form(category_id=str(services.id), price="", price_unit="a convenir", attr_zona="Vélez", attr_sexo=""),
        User.by_phone("3101112233"),
    )
    assert "price" not in errors


def test_village_must_belong_to_municipality(app):
    barbosa_village = Village.query.join(Municipality).filter(Municipality.slug == "barbosa").first()
    _, errors = parse(village_id=str(barbosa_village.id))
    assert "village_id" in errors
    velez_village = Village.query.join(Municipality).filter(Municipality.slug == "velez").first()
    assert "village_id" not in parse(village_id=str(velez_village.id))[1]


def test_step_for_error_opens_first_step_with_problem():
    assert step_for_error({}) == 1
    assert step_for_error({"price": "x"}) == 4
    assert step_for_error({"price": "x", "attr_sexo": "x"}) == 2
    assert step_for_error({"price": "x", "title": "x"}) == 1


def test_values_roundtrip_for_edit_and_duplicate(app):
    listing = Listing.query.filter(Listing.title.contains("Novillo cebú")).first()
    values = values_from_listing(listing)
    assert values["attr_edad"] == "18" and values["attr_edad__unit"] == "meses"
    assert values["attr_vacunacion"] == "si" and values["category_id"] == str(listing.category_id)
    data, errors = parse_listing_form(values, listing.user)
    assert not errors and data["attrs"]["edad"] == 18


def test_apply_images_ordering_removal_and_limit(app):
    listing = Listing.query.first()
    new = MultiDict([("photos", _file("a.png")), ("photos", _file("b.png"))])
    assert apply_images(listing, {"image_order_set": "1", "image_order": "n1,n0"}, new) == []
    db.session.commit()
    assert [i.position for i in listing.images] == [0, 1] and len(listing.images) == 2
    first_id = listing.images[0].id
    errors = apply_images(listing, {"image_order_set": "1", "image_order": f"e{first_id}"}, MultiDict())
    assert errors == [] and [i.id for i in listing.images] == [first_id]
    too_many = ",".join(f"n{i}" for i in range(7))
    many = MultiDict([("photos", _file(f"{i}.png")) for i in range(7)])
    assert "máximo 6" in apply_images(listing, {"image_order_set": "1", "image_order": too_many}, many)[0]


def _file(name):
    from werkzeug.datastructures import FileStorage

    return FileStorage(stream=png_bytes((300, 300)), filename=name, content_type="image/png")

from app.models import Category
from app.services.attributes import format_age, validate_attrs


def test_attrs_valid_and_age_in_months(app):
    category = Category.query.filter_by(slug="novillos").first()
    clean, errors = validate_attrs(
        category,
        {"attr_sexo": "Macho", "attr_edad": "2", "attr_edad__unit": "años", "attr_peso": "300",
         "attr_vacunacion": "si", "attr_inventado": "x"},
    )  # fmt: skip
    assert not errors
    assert clean == {"sexo": "Macho", "edad": 24, "peso": 300, "vacunacion": True}


def test_attrs_required_choice_and_range(app):
    category = Category.query.filter_by(slug="terneros").first()  # «Terneros» sí pregunta el sexo
    _, errors = validate_attrs(category, {})
    assert "attr_sexo" in errors
    _, errors = validate_attrs(category, {"attr_sexo": "Otro", "attr_peso": "99999"})
    assert "attr_sexo" in errors and "attr_peso" in errors


def test_attrs_of_other_category_are_ignored(app):
    category = Category.query.filter_by(slug="frutas").first()
    clean, errors = validate_attrs(category, {"attr_sexo": "Macho", "attr_calidad": "Primera"})
    assert clean == {"calidad": "Primera"} and not errors


def test_bool_and_age_validation_messages(app):
    category = Category.query.filter_by(slug="novillos").first()
    _, errors = validate_attrs(category, {"attr_sexo": "Macho", "attr_vacunacion": "tal vez"})
    assert "Sí o No" in errors["attr_vacunacion"]
    _, errors = validate_attrs(category, {"attr_sexo": "Macho", "attr_edad": "9999", "attr_edad__unit": "años"})
    assert "edad" in errors["attr_edad"]


def test_format_age():
    assert format_age(1) == "1 mes"
    assert format_age(18) == "1 año y 6 meses"
    assert format_age(24) == "2 años"

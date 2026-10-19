"""Atributos dinámicos por categoría: definiciones en BD, valores en Listing.attrs (JSON/JSONB)."""

import math
from collections.abc import Callable, Mapping
from typing import Any

from ..constants import AGE_MAX_MONTHS, ATTR_TEXT_MAX, OTHER_CHOICES
from ..models import AttributeDef, Category, Listing
from ..utils import parse_int


def defs_for(category: Category | None) -> list[AttributeDef]:
    """Definiciones activas de la categoría raíz + las propias de la subcategoría."""
    if category is None:
        return []
    ids = {category.id}
    if category.parent_id:
        ids.add(category.parent_id)
    return (
        AttributeDef.query.filter(AttributeDef.category_id.in_(ids), AttributeDef.is_active.is_(True))
        .order_by(AttributeDef.position, AttributeDef.id)
        .all()
    )


def is_shown(d: AttributeDef, value_of: Callable[[str], Any]) -> bool:
    """¿Se pregunta (y se muestra) este dato? Los condicionales (p. ej. «Preñada») solo aplican si el dato del que
    dependen (`show_if_key`, p. ej. «sexo») tiene uno de los valores de `show_if_values` (p. ej. «Hembra»).

    `value_of(clave)` devuelve el valor actual de otro dato: del formulario al validar, o de los guardados al mostrar.
    """
    if not d.show_if_key:
        return True
    value = value_of(d.show_if_key)
    if isinstance(value, bool):  # los Sí/No se guardan como True/False y se envían como «si»/«no»
        value = "si" if value else "no"
    return str(value or "").strip() in (d.show_if_values or [])


def visible_defs(category: Category | None, value_of: Callable[[str], Any]) -> list[AttributeDef]:
    """Los datos que aplican a esta categoría con las respuestas actuales, en orden.

    Las reglas se encadenan: un dato oculto cuenta como «sin respuesta» para los que dependen de él (si no está
    preñada no se pregunta cuántos meses de gestación). Los datos que fija la subcategoría (`fixed_attrs`: «Toros» →
    sexo Macho) cuentan como respondidos con ese valor, diga lo que diga el formulario."""
    fixed = (category.fixed_attrs or {}) if category else {}
    shown: dict[str, bool] = {}

    def answer(key: str) -> Any:
        if key in fixed:
            return fixed[key]
        return value_of(key) if shown.get(key, True) else None

    result = []
    for d in defs_for(category):
        shown[d.key] = is_shown(d, answer)
        if shown[d.key]:
            result.append(d)
    return result


def _number(raw: str, d: AttributeDef, as_int: bool) -> int | float:
    try:
        value = parse_int(raw) if as_int else float(raw.replace(",", "."))
    except ValueError:
        raise ValueError("Escribe solo números.") from None
    if not math.isfinite(value):
        raise ValueError("Escribe solo números.")
    if d.min_value is not None and value < d.min_value:
        raise ValueError(f"Debe ser mínimo {d.min_value:g}.")
    if d.max_value is not None and value > d.max_value:
        raise ValueError(f"Debe ser máximo {d.max_value:g}.")
    return value


def _age_in_months(raw: str, d: AttributeDef, form: Mapping[str, str]) -> int:
    try:
        n = parse_int(raw)
    except ValueError:
        raise ValueError("Escribe solo números.") from None
    unit = form.get(f"attr_{d.key}__unit", "meses")
    if unit not in ("meses", "años"):
        raise ValueError("Elige meses o años.")
    months = n * 12 if unit == "años" else n
    if months > AGE_MAX_MONTHS:
        raise ValueError("La edad no parece correcta.")
    return months


def coerce(d: AttributeDef, raw: str, form: Mapping[str, str]) -> Any:
    """Convierte el texto del formulario al tipo del atributo. Lanza ValueError con mensaje en español."""
    if d.type == "text":
        if len(raw) > ATTR_TEXT_MAX:
            raise ValueError(f"Es muy largo (máximo {ATTR_TEXT_MAX} letras).")
        return raw
    if d.type == "int":
        return _number(raw, d, True)
    if d.type == "decimal":
        return _number(raw, d, False)
    if d.type == "bool":
        if raw not in ("si", "no"):
            raise ValueError("Elige Sí o No.")
        return raw == "si"
    if d.type == "choice":
        if raw not in (d.choices or []):
            raise ValueError("Elige una de las opciones.")
        return raw
    if d.type == "age":
        return _age_in_months(raw, d, form)
    raise ValueError("Tipo de dato desconocido.")


def validate_attrs(category: Category, form: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
    """Valida los datos específicos contra las definiciones. Devuelve (limpios, errores).
    Las claves desconocidas se ignoran (nunca se guardan). Un dato condicional que no aplica (p. ej. «Preñada» en un
    macho) no se exige ni se guarda, aunque llegue en el formulario."""
    clean: dict[str, Any] = {}
    errors: dict[str, str] = {}
    fixed = category.fixed_attrs or {}
    for d in visible_defs(category, lambda key: form.get(f"attr_{key}")):
        raw = str(fixed[d.key]) if d.key in fixed else (form.get(f"attr_{d.key}") or "").strip()
        if raw == "":
            if d.required:
                errors[f"attr_{d.key}"] = "Este dato es obligatorio."
            continue
        try:
            clean[d.key] = coerce(d, raw, form)
        except ValueError as e:
            errors[f"attr_{d.key}"] = str(e)
            continue
        if d.type == "choice" and is_other_choice(raw):
            _store_other(d, form, clean, errors)
    return clean, errors


def is_other_choice(value: str) -> bool:
    """¿Es una opción tipo «Otra»/«Otro», que pide escribir cuál es?"""
    return value.strip().lower() in OTHER_CHOICES


def _other_key(key: str) -> str:
    return f"{key}__other"


def _store_other(d: AttributeDef, form: Mapping[str, str], clean: dict[str, Any], errors: dict[str, str]) -> None:
    text = " ".join((form.get(f"attr_{_other_key(d.key)}") or "").split())
    if not text:
        errors[f"attr_{d.key}"] = "Escribe cuál es."
    elif len(text) > ATTR_TEXT_MAX:
        errors[f"attr_{d.key}"] = f"Es muy largo (máximo {ATTR_TEXT_MAX} letras)."
    else:
        clean[_other_key(d.key)] = text


def format_age(months: int) -> str:
    months = int(months)
    if months < 12:
        return f"{months} {'mes' if months == 1 else 'meses'}"
    years, rest = divmod(months, 12)
    text = f"{years} {'año' if years == 1 else 'años'}"
    return text + (f" y {rest} {'mes' if rest == 1 else 'meses'}" if rest else "")


def format_value(d: AttributeDef, value: Any) -> str:
    if d.type == "bool":
        return "Sí" if value else "No"
    if d.type == "age":
        return format_age(value)
    if d.type in ("int", "decimal"):
        is_whole = float(value).is_integer()
        text = f"{value:,.0f}".replace(",", ".") if is_whole else f"{value:,.2f}"
        return f"{text} {d.unit}" if d.unit else text
    return str(value)


def display_attrs(listing: Listing) -> list[tuple[str, str]]:
    """Lista [(etiqueta, valor_formateado)] para la ficha de detalle."""
    values = listing.attrs or {}
    rows = []
    for d in visible_defs(listing.category, values.get):
        if d.key not in values:
            continue
        text = format_value(d, values[d.key])
        other = values.get(_other_key(d.key))
        rows.append((d.label, f"{text}: {other}" if other else text))
    return rows


def form_values_from_attrs(category: Category, attrs: dict[str, Any] | None) -> dict[str, str]:
    """Convierte attrs guardados en valores de formulario (para editar/duplicar)."""
    out: dict[str, str] = {}
    attrs = attrs or {}
    for d in visible_defs(category, attrs.get):
        if d.key not in attrs:
            continue
        v = attrs[d.key]
        if d.type == "bool":
            out[f"attr_{d.key}"] = "si" if v else "no"
        elif d.type == "age":
            years = v >= 12 and v % 12 == 0
            out[f"attr_{d.key}"] = str(v // 12 if years else v)
            out[f"attr_{d.key}__unit"] = "años" if years else "meses"
        else:
            out[f"attr_{d.key}"] = str(v)
        if attrs.get(_other_key(d.key)):
            out[f"attr_{_other_key(d.key)}"] = attrs[_other_key(d.key)]
    return out

import math

from wtforms import BooleanField, IntegerField, SelectField, StringField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from ...constants import ATTR_TYPES, CATEGORY_ICONS, HOME_SECTIONS
from ...forms import BaseForm
from ...models import AttributeDef, Category
from ...services import geo
from ...utils import slugify


def _parse_float(raw: str | None) -> float | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    value = float(raw.replace(",", "."))
    if not math.isfinite(value):
        raise ValueError(raw)
    return value


class CategoryForm(BaseForm):
    """Categoría o subcategoría. Los campos de unidades, sección e ICA solo aplican a categorías raíz."""

    name = StringField("Nombre", validators=[DataRequired("Escribe el nombre."), Length(max=80)])
    icon = SelectField("Icono", choices=[(i, i) for i in CATEGORY_ICONS], default="campo")
    price_units = StringField("Unidades de precio (separadas por coma)", validators=[Optional()])
    home_section = SelectField(
        "Sección en el inicio", choices=[("", "Ninguna"), *HOME_SECTIONS.items()], validate_choice=False, default=""
    )
    requires_ica = BooleanField("Muestra aviso de guía sanitaria ICA")
    position = IntegerField("Orden", validators=[Optional()], default=0)
    is_active = BooleanField("Visible", default=True)

    def __init__(self, *args, category: Category | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.category = category

    def validate_name(self, field: StringField) -> None:
        clash = Category.query.filter_by(slug=slugify(field.data)).first()
        if clash and (not self.category or clash.id != self.category.id):
            raise ValidationError("Ya existe una categoría con ese nombre.")


class AttributeForm(BaseForm):
    """Dato específico de una categoría (raza, sexo, peso…)."""

    label = StringField(
        "Nombre que ve la gente", validators=[DataRequired("Escribe el nombre del dato."), Length(max=80)]
    )
    key = StringField("Clave interna (opcional)", validators=[Optional(), Length(max=40)])
    type = SelectField("Tipo de dato", choices=list(ATTR_TYPES.items()), validators=[DataRequired("Elige el tipo.")])
    choices = StringField("Opciones (solo para «Lista de opciones»)", validators=[Optional()])
    unit = StringField("Unidad (opcional)", validators=[Optional(), Length(max=20)])
    min_value = StringField("Mínimo", validators=[Optional()])
    max_value = StringField("Máximo", validators=[Optional()])
    help_text = StringField("Ayuda bajo el campo", validators=[Optional(), Length(max=160)])
    position = IntegerField("Orden", validators=[Optional()])
    required = BooleanField("Obligatorio")
    is_filterable = BooleanField("Usar como filtro en el listado")
    is_active = BooleanField("Visible", default=True)

    def __init__(self, *args, category: Category, attr: AttributeDef | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.category, self.attr = category, attr

    def validate_key(self, field: StringField) -> None:
        if self.attr:
            return
        key = self.computed_key
        if AttributeDef.query.filter_by(category_id=self.category.id, key=key).first():
            raise ValidationError("Ya existe un dato con esa clave en esta categoría.")

    @property
    def computed_key(self) -> str:
        return self.attr.key if self.attr else slugify(self.key.data or self.label.data).replace("-", "_")

    def option_list(self) -> list[str]:
        return [c.strip() for c in (self.choices.data or "").split(",") if c.strip()]

    def validate_choices(self, field: StringField) -> None:
        if self.type.data == "choice" and len(self.option_list()) < 2:
            raise ValidationError("Escribe al menos 2 opciones separadas por coma.")

    def _validate_number(self, field: StringField) -> None:
        try:
            _parse_float(field.data)
        except ValueError:
            raise ValidationError("Escribe un número.") from None

    validate_min_value = validate_max_value = _validate_number

    @property
    def min_number(self) -> float | None:
        return _parse_float(self.min_value.data)

    @property
    def max_number(self) -> float | None:
        return _parse_float(self.max_value.data)


class MunicipalityForm(BaseForm):
    name = StringField("Nuevo municipio", validators=[DataRequired("Escribe el nombre del municipio."), Length(max=80)])
    department = StringField("Departamento", default="Santander", validators=[Optional(), Length(max=60)])


class CoordinatesForm(BaseForm):
    """Centro aproximado de un municipio o vereda (para el mapa y «cerca de mí»)."""

    lat = StringField("Latitud")
    lng = StringField("Longitud")
    point: tuple[float, float] | None = None

    def validate_lng(self, field: StringField) -> None:
        try:
            self.point = geo.parse_point(self.lat.data, field.data)
        except ValueError as error:
            raise ValidationError(str(error)) from None


class VillageForm(BaseForm):
    name = StringField("Nueva vereda", validators=[DataRequired("Escribe el nombre de la vereda."), Length(max=80)])

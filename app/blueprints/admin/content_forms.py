"""Formularios del admin para la agenda y los consejos."""

from flask_wtf.file import FileField
from wtforms import BooleanField, DateTimeLocalField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from ...constants import (
    ARTICLE_CATEGORIES,
    ARTICLE_SUMMARY_MAX,
    ARTICLE_TITLE_MAX,
    EVENT_KINDS,
)
from ...forms import BaseForm

LOCAL_FORMAT = "%Y-%m-%dT%H:%M"


class EventForm(BaseForm):
    title = StringField("Nombre del evento", validators=[DataRequired("Escribe el nombre."), Length(max=120)])
    kind = SelectField("Tipo de evento", choices=list(EVENT_KINDS.items()))
    starts_at = DateTimeLocalField(
        "Empieza", format=LOCAL_FORMAT, validators=[DataRequired("Elige la fecha y hora en que empieza.")]
    )
    ends_at = DateTimeLocalField("Termina (opcional)", format=LOCAL_FORMAT, validators=[Optional()])
    place = StringField("Lugar", validators=[Optional(), Length(max=160)])
    municipality_id = SelectField("Municipio", coerce=lambda v: int(v) if v else 0, validate_choice=False)
    organizer = StringField("Quién lo organiza (SENA, ICA, alcaldía…)", validators=[Optional(), Length(max=120)])
    description = TextAreaField("Descripción", validators=[Optional(), Length(max=2000)])
    image = FileField("Imagen (opcional)")
    remove_image = BooleanField("Quitar la imagen actual")
    is_published = BooleanField("Publicado (visible para todos)", default=True)

    def validate_ends_at(self, field: DateTimeLocalField) -> None:
        if field.data and self.starts_at.data and field.data < self.starts_at.data:
            raise ValidationError("Debe terminar después de empezar.")


class ArticleForm(BaseForm):
    title = StringField("Título", validators=[DataRequired("Escribe el título."), Length(max=ARTICLE_TITLE_MAX)])
    category = SelectField("Tema", choices=list(ARTICLE_CATEGORIES.items()))
    summary = TextAreaField(
        "Resumen (aparece en la lista y al compartir)",
        validators=[DataRequired("Escribe un resumen corto."), Length(max=ARTICLE_SUMMARY_MAX)],
    )
    body = TextAreaField("Contenido", validators=[DataRequired("Escribe el contenido del artículo.")])
    cover = FileField("Portada (opcional)")
    remove_cover = BooleanField("Quitar la portada actual")
    is_published = BooleanField("Publicado (visible para todos)", default=True)

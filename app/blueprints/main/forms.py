import re

from wtforms import SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, ValidationError

from ...constants import (
    CONTACT_MESSAGE_MAX,
    CONTACT_MESSAGE_MIN,
    CONTACT_SUBJECTS,
    NAME_MAX,
    NAME_MIN,
)
from ...forms import BaseForm
from ...utils import normalize_phone

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class ContactForm(BaseForm):
    name = StringField("Tu nombre", validators=[DataRequired("Escribe tu nombre."), Length(NAME_MIN, NAME_MAX)])
    contact = StringField(
        "Tu celular o correo",
        validators=[DataRequired("Escribe un celular o correo para responderte."), Length(max=120)],
    )
    subject = SelectField("¿Sobre qué quieres escribirnos?", choices=list(CONTACT_SUBJECTS.items()))
    message = TextAreaField(
        "Tu mensaje",
        validators=[
            DataRequired("Cuéntanos qué necesitas."),
            Length(
                CONTACT_MESSAGE_MIN,
                CONTACT_MESSAGE_MAX,
                f"Escribe entre {CONTACT_MESSAGE_MIN} y {CONTACT_MESSAGE_MAX} letras.",
            ),
        ],
    )

    def validate_contact(self, field: StringField) -> None:
        value = (field.data or "").strip()
        if not normalize_phone(value) and not EMAIL_PATTERN.fullmatch(value):
            raise ValidationError("Escribe un celular de 10 números (3101234567) o un correo válido.")

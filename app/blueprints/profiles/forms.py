from flask import request
from flask_login import current_user
from flask_wtf.file import FileField
from wtforms import BooleanField, IntegerField, PasswordField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

from ...constants import (
    BIO_MAX,
    EMAIL_MAX,
    FARM_NAME_MAX,
    NAME_MAX,
    NAME_MIN,
    PASSWORD_MAX,
    PASSWORD_MIN,
    RATING_COMMENT_MAX,
    RATING_MAX,
    RATING_MIN,
    VILLAGE_OTHER_MAX,
)
from ...extensions import db
from ...forms import BaseForm, validate_optional_email
from ...models import Municipality, User
from ...services.listing_form import parse_listing_form
from ...services.places import resolve_village


class ListingForm(BaseForm):
    """Publicar/editar: CSRF + validación dinámica según la categoría (ver services.listing_form).

    Los campos específicos cambian con la categoría, por eso no se declaran uno a uno: tras validar,
    `cleaned` trae los datos listos y `field_errors` los errores por campo."""

    def __init__(self, user: User, **kwargs) -> None:
        super().__init__(**kwargs)
        self.user = user
        self.cleaned: dict = {}
        self.field_errors: dict[str, str] = {}

    def validate(self, extra_validators=None) -> bool:
        csrf_ok = super().validate(extra_validators)
        self.cleaned, self.field_errors = parse_listing_form(request.form, self.user)
        return csrf_ok and not self.field_errors


class DeleteAccountForm(BaseForm):
    password = PasswordField("Tu contraseña", validators=[DataRequired("Escribe tu contraseña para confirmar.")])
    confirm = BooleanField(
        "Entiendo que se borran mis anuncios y que esto no se puede deshacer",
        validators=[DataRequired("Marca la casilla para confirmar.")],
    )


class ChangePasswordForm(BaseForm):
    current_password = PasswordField("Tu contraseña actual", validators=[DataRequired("Escribe tu contraseña actual.")])
    password = PasswordField(
        "Contraseña nueva",
        validators=[
            DataRequired("Escribe tu contraseña nueva."),
            Length(PASSWORD_MIN, PASSWORD_MAX, f"Mínimo {PASSWORD_MIN} letras o números."),
        ],
    )
    confirm = PasswordField(
        "Repite la contraseña nueva",
        validators=[
            DataRequired("Repite la contraseña nueva."),
            EqualTo("password", "Las contraseñas no son iguales."),
        ],
    )


class RatingForm(BaseForm):
    stars = RadioField(
        "Tu calificación",
        choices=[(str(n), str(n)) for n in range(RATING_MIN, RATING_MAX + 1)],
        validators=[DataRequired("Elige de 1 a 5 estrellas.")],
    )
    comment = TextAreaField(
        "Cuéntanos tu experiencia (opcional)", validators=[Optional(), Length(max=RATING_COMMENT_MAX)]
    )


class ProfileForm(BaseForm):
    name = StringField("Tu nombre", validators=[DataRequired("Escribe tu nombre."), Length(NAME_MIN, NAME_MAX)])
    farm_name = StringField("Nombre de la finca (opcional)", validators=[Optional(), Length(max=FARM_NAME_MAX)])
    email = StringField("Correo electrónico (opcional)", validators=[Length(max=EMAIL_MAX)])
    municipality_id = SelectField("Municipio", coerce=int, validators=[DataRequired("Elige tu municipio.")])
    village_id = IntegerField("Vereda", validators=[Optional()])
    # Sin Optional(): si lo llevara, validate_village_other no correría con el campo vacío
    village_other = StringField("¿Cómo se llama tu vereda?", validators=[Length(max=VILLAGE_OTHER_MAX)])
    bio = TextAreaField("Cuéntales quién eres (opcional)", validators=[Optional(), Length(max=BIO_MAX)])
    photo = FileField("Foto de perfil o de tu finca (opcional)")
    remove_photo = BooleanField("Quitar mi foto actual")

    def validate_email(self, field: StringField) -> None:
        validate_optional_email(field, own_user_id=current_user.id)

    def validate_municipality_id(self, field: SelectField) -> None:
        if not db.session.get(Municipality, field.data):
            raise ValidationError("Elige tu municipio.")

    def validate_village_other(self, field: StringField) -> None:
        _, _, error = resolve_village(self.village_id.data, field.data, self.municipality_id.data)
        if error and error[0] == "village_other":
            raise ValidationError(error[1])

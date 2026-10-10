from wtforms import (
    BooleanField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
)
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from ...constants import (
    EMAIL_MAX,
    FARM_NAME_MAX,
    NAME_MAX,
    NAME_MIN,
    PASSWORD_MAX,
    PASSWORD_MIN,
    VILLAGE_OTHER_MAX,
)
from ...extensions import db
from ...forms import BaseForm, validate_optional_email
from ...models import Municipality, User
from ...services.places import resolve_village
from ...utils import normalize_phone

MSG_PHONE = "Escribe tu celular de 10 números, que empieza por 3. Ej: 3101234567"


class LoginForm(BaseForm):
    phone = StringField("Celular", validators=[DataRequired("Escribe tu celular.")])
    password = PasswordField("Contraseña", validators=[DataRequired("Escribe tu contraseña.")])
    remember = BooleanField("Mantener sesión iniciada", default=True)


CODE_VALIDATORS = [DataRequired("Escribe el código que te enviamos."), Length(6, 6, "El código tiene 6 números.")]


class VerifyCodeForm(BaseForm):
    code = StringField("Código de 6 números", validators=CODE_VALIDATORS)


class ForgotPasswordForm(BaseForm):
    phone = StringField("Tu celular", validators=[DataRequired("Escribe tu celular.")])


class ResetPasswordForm(BaseForm):
    code = StringField("Código de 6 números", validators=CODE_VALIDATORS)
    password = PasswordField(
        "Contraseña nueva",
        validators=[
            DataRequired("Escribe tu contraseña nueva."),
            Length(PASSWORD_MIN, PASSWORD_MAX, f"Mínimo {PASSWORD_MIN} letras o números."),
        ],
    )


class RegisterForm(BaseForm):
    name = StringField("Tu nombre", validators=[DataRequired("Escribe tu nombre."), Length(NAME_MIN, NAME_MAX)])
    phone = StringField("Celular (WhatsApp)", validators=[DataRequired("Escribe tu celular.")])
    password = PasswordField(
        "Contraseña",
        validators=[
            DataRequired("Crea una contraseña."),
            Length(PASSWORD_MIN, PASSWORD_MAX, f"Mínimo {PASSWORD_MIN} letras o números."),
        ],
    )
    email = StringField("Correo electrónico (opcional)", validators=[Length(max=EMAIL_MAX)])
    municipality_id = SelectField("Municipio", coerce=int, validators=[DataRequired("Elige tu municipio.")])
    village_id = IntegerField("Vereda", validators=[Optional()])
    # Sin Optional(): si lo llevara, validate_village_other no correría con el campo vacío
    village_other = StringField("¿Cómo se llama tu vereda?", validators=[Length(max=VILLAGE_OTHER_MAX)])
    farm_name = StringField("Nombre de la finca (opcional)", validators=[Optional(), Length(max=FARM_NAME_MAX)])
    accept_terms = BooleanField(
        "Acepto los términos y la política de datos personales",
        validators=[DataRequired("Debes aceptar los términos y la política de datos para crear tu cuenta.")],
    )

    def validate_phone(self, field: StringField) -> None:
        phone = normalize_phone(field.data)
        if not phone:
            raise ValidationError(MSG_PHONE)
        if User.by_phone(phone):
            raise ValidationError("Ese celular ya tiene cuenta. Ingresa con tu contraseña.")

    def validate_email(self, field: StringField) -> None:
        validate_optional_email(field)

    def validate_municipality_id(self, field: SelectField) -> None:
        if not db.session.get(Municipality, field.data):
            raise ValidationError("Elige tu municipio.")

    def validate_village_other(self, field: StringField) -> None:
        _, _, error = resolve_village(self.village_id.data, field.data, self.municipality_id.data)
        if error and error[0] == "village_other":
            raise ValidationError(error[1])

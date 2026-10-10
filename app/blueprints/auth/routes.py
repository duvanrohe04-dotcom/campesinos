from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ...constants import RESET_SESSION_KEY
from ...extensions import limiter
from ...models import Municipality, User, Village
from ...services import verification
from ...utils import is_safe_next, normalize_phone
from . import bp, services
from .forms import ForgotPasswordForm, LoginForm, RegisterForm, ResetPasswordForm, VerifyCodeForm


def _send_verification_code(user: User) -> bool:
    """Envía el código de verificación al correo. Si falla, avisa con un mensaje claro. Devuelve si salió."""
    try:
        verification.send_code(user)
    except verification.VerificationError as error:
        flash(str(error), "error")
        return False
    return True


@bp.route("/registro", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["REGISTER_RATE_LIMIT"], methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = RegisterForm()
    form.municipality_id.choices = [(m.id, m.name) for m in Municipality.ordered()]
    if form.validate_on_submit():
        user = services.register_user(form)
        login_user(user, remember=True)
        flash("¡Bienvenido! Tu cuenta está lista: ya puedes comprar, vender o buscar lo que necesites.", "success")
        if user.email and _send_verification_code(user):
            flash("Te enviamos un código a tu correo. Escríbelo aquí para verificarlo.", "info")
            return redirect(url_for("auth.verify_email"))
        return redirect(url_for("main.home"))
    return render_template("auth/register.html", form=form, villages=Village.ordered())


@bp.route("/ingresar", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"], methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = LoginForm()
    if form.validate_on_submit():
        result, user = services.authenticate(form.phone.data, form.password.data)
        if result is services.LoginResult.OK:
            login_user(user, remember=form.remember.data)
            target = request.args.get("next")
            return redirect(target if is_safe_next(target) else url_for("main.home"))
        if result is services.LoginResult.LOCKED:
            flash("Demasiados intentos. Espera unos minutos e inténtalo de nuevo.", "error")
        elif result is services.LoginResult.DISABLED:
            flash(
                "Tu cuenta está suspendida. Escríbenos desde Contacto para saber por qué y cómo reactivarla.", "error"
            )
        else:
            flash("Celular o contraseña incorrectos.", "error")
    return render_template("auth/login.html", form=form)


# ---------- Verificar el correo ----------
@bp.route("/verificar-correo", methods=["GET", "POST"])
@login_required
def verify_email():
    """Pide el código que llegó al correo y lo confirma."""
    if current_user.email_verified:
        flash("Tu correo ya está verificado.", "success")
        return redirect(url_for("profiles.panel"))
    if not current_user.email:
        flash("Agrega tu correo para poder verificarlo.", "info")
        return redirect(url_for("profiles.edit_profile"))
    form = VerifyCodeForm()
    if form.validate_on_submit():
        try:
            verification.confirm_code(current_user, form.code.data)
        except verification.VerificationError as error:
            flash(str(error), "error")
        else:
            flash("¡Listo! Tu correo quedó verificado.", "success")
            return redirect(url_for("profiles.panel"))
    return render_template("auth/verify_email.html", form=form, wait=verification.seconds_until_resend(current_user))


@bp.route("/verificar-correo/enviar", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["VERIFY_RATE_LIMIT"])
def send_verification_code():
    if _send_verification_code(current_user):
        flash("Te enviamos un código de 6 números a tu correo. Revisa también la carpeta de spam.", "success")
    return redirect(url_for("auth.verify_email"))


@bp.route("/verificar-celular", methods=["GET", "POST"])
def legacy_verify_phone():
    """Dirección anterior: el celular ya no se verifica; ahora se verifica el correo."""
    return redirect(url_for("auth.verify_email"), code=308)


# ---------- Recuperar la contraseña ----------
@bp.route("/recuperar", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["VERIFY_RATE_LIMIT"], methods=["POST"])
def forgot_password():
    """Paso 1: la persona escribe su celular y, si tiene un correo verificado, recibe un código."""
    if current_user.is_authenticated:
        return redirect(url_for("profiles.edit_profile"))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        services.request_password_reset(form.phone.data)
        session[RESET_SESSION_KEY] = normalize_phone(form.phone.data) or ""
        return redirect(url_for("auth.reset_password"))
    return render_template("auth/forgot_password.html", form=form)


@bp.route("/recuperar/codigo", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"], methods=["POST"])
def reset_password():
    """Paso 2: código del correo + contraseña nueva."""
    if current_user.is_authenticated:
        return redirect(url_for("profiles.edit_profile"))
    if RESET_SESSION_KEY not in session:
        return redirect(url_for("auth.forgot_password"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            services.reset_password(session[RESET_SESSION_KEY], form.code.data, form.password.data)
        except verification.VerificationError as error:
            flash(str(error), "error")
        else:
            session.pop(RESET_SESSION_KEY, None)
            flash("¡Listo! Ya puedes ingresar con tu contraseña nueva.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)


@bp.route("/salir", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Cerraste sesión. ¡Hasta pronto!", "info")
    return redirect(url_for("main.home"))

import json

from flask import Response, abort, current_app, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user

from ...decorators import get_owned_listing, owner_required
from ...extensions import db, limiter
from ...forms import form_errors, form_values
from ...models import Municipality, User, Village
from ...services import account as account_service
from ...services import ratings
from ...utils import whatsapp_url
from . import bp, services
from .forms import ChangePasswordForm, DeleteAccountForm, ListingForm, ProfileForm, RatingForm

INVALID_FORM_MESSAGE = "Revisa los datos marcados en rojo."


# ---------- Panel del vendedor ----------
@bp.route("/panel")
@login_required
def panel():
    summary = services.panel_summary(current_user)
    return render_template(
        "profiles/panel.html",
        items=summary.items,
        stats=summary.stats,
        expiring=summary.expiring,
        weekly=summary.weekly,
    )


@bp.route("/publicar", methods=["GET", "POST"])
@login_required
@limiter.limit(lambda: current_app.config["PUBLISH_RATE_LIMIT"], methods=["POST"])
def new_listing():
    blocked = services.publish_block_reason(current_user)
    if blocked:
        flash(blocked, "error")
        return redirect(url_for("profiles.panel"))
    form = ListingForm(current_user)
    values, errors = services.initial_values(current_user, request.args.get("tipo", "")), {}
    copy_id = request.args.get("copiar", "")
    if request.method == "GET" and copy_id.isdigit():
        source = get_owned_listing(int(copy_id))
        values = services.copy_values(source)
        flash("Copiamos tu anuncio anterior. Cambia lo que haga falta y publica.", "info")
    elif request.method == "POST":
        values = request.form.to_dict()
        if form.validate_on_submit():
            listing, photo_error = services.create_listing(current_user, form.cleaned, request.form, request.files)
            if listing:
                return redirect(url_for("profiles.listing_done", listing_id=listing.id))
            errors = {"photos": photo_error}
        else:
            errors = form.field_errors
        flash(INVALID_FORM_MESSAGE, "error")
    return render_template("profiles/listing_form.html", **services.listing_form_context(current_user, values, errors))


@bp.route("/panel/anuncio/<int:listing_id>/editar", methods=["GET", "POST"])
@owner_required
def edit_listing(listing):
    form = ListingForm(listing.user)
    values, errors = services.copy_values(listing), {}
    if request.method == "POST":
        values = request.form.to_dict()
        if form.validate_on_submit():
            photo_error = services.update_listing(listing, form.cleaned, request.form, request.files)
            if not photo_error:
                flash("Cambios guardados.", "success")
                return redirect(url_for("profiles.panel"))
            errors = {"photos": photo_error}
        else:
            errors = form.field_errors
        flash(INVALID_FORM_MESSAGE, "error")
    return render_template(
        "profiles/listing_form.html",
        **services.listing_form_context(listing.user, values, errors, listing, editing=True),
    )


@bp.route("/panel/anuncio/<int:listing_id>/listo")
@owner_required
def listing_done(listing):
    share_url, whatsapp_share = services.share_link(listing)
    return render_template("profiles/listing_done.html", l=listing, share_url=share_url, wa_share=whatsapp_share)


@bp.route("/panel/anuncio/<int:listing_id>/<action>", methods=["POST"])
@owner_required
def listing_action(listing, action):
    try:
        flash(services.perform_action(listing, action), "success")
    except services.ActionBlockedError as error:
        flash(str(error), "error")
    except ValueError:
        abort(404)
    return redirect(url_for("profiles.panel"))


# ---------- Perfil propio ----------
@bp.route("/panel/perfil", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = ProfileForm(obj=current_user if request.method == "GET" else None)
    form.municipality_id.choices = [(m.id, m.name) for m in Municipality.ordered()]
    if form.validate_on_submit():
        previous_email = current_user.email
        photo_error = services.update_profile(current_user, form, request.files.get("photo"))
        if photo_error:
            flash(photo_error, "error")
        else:
            flash("Perfil actualizado.", "success")
            if current_user.email and current_user.email != previous_email:  # correo nuevo: pedir verificarlo
                email_error = services.send_email_verification(current_user)
                flash(email_error or "Te enviamos un código a tu correo. Escríbelo para verificarlo.", "info")
                return redirect(url_for("auth.verify_email" if not email_error else "profiles.panel"))
            return redirect(url_for("profiles.panel"))
    return render_template(
        "profiles/edit_profile.html",
        form=form,
        values=form_values(form),
        errors=form_errors(form),
        municipalities=Municipality.ordered(),
        villages=Village.ordered(),
    )


# ---------- Cambiar la contraseña ----------
@bp.route("/panel/contrasena", methods=["GET", "POST"])
@login_required
@limiter.limit(lambda: current_app.config["ACCOUNT_RATE_LIMIT"], methods=["POST"])
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if services.change_password(current_user, form.current_password.data, form.password.data):
            flash("Listo: tu contraseña nueva ya está activa.", "success")
            return redirect(url_for("profiles.panel"))
        form.current_password.errors.append("Esa no es tu contraseña actual.")
    return render_template("profiles/change_password.html", form=form)


# ---------- Perfil público del vendedor ----------
@bp.route("/vendedor/<int:user_id>")
def public(user_id):
    seller, listings, sold = services.seller_page(user_id)
    if not seller:
        abort(404)
    own = ratings.own_rating(seller, current_user) if current_user.is_authenticated else None
    form = RatingForm(data={"stars": str(own.stars), "comment": own.comment} if own else None)
    return render_template(
        "profiles/public.html",
        seller=seller,
        listings=listings,
        sold=sold,
        reputation=ratings.reputation(seller),
        reviews=ratings.visible_reviews(seller),
        own_rating=own,
        rating_form=form,
    )


# ---------- Mis datos (Ley 1581): descargar y eliminar la cuenta ----------
@bp.route("/panel/cuenta")
@login_required
def account():
    return render_template("profiles/account.html", form=DeleteAccountForm())


@bp.route("/panel/cuenta/exportar")
@login_required
@limiter.limit(lambda: current_app.config["ACCOUNT_RATE_LIMIT"])
def export_account():
    payload = json.dumps(account_service.export_user_data(current_user), ensure_ascii=False, indent=2)
    response = Response(payload, mimetype="application/json")
    response.headers["Content-Disposition"] = 'attachment; filename="mis-datos-campo-directo.json"'
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/panel/cuenta/eliminar", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["ACCOUNT_RATE_LIMIT"])
def delete_account():
    if current_user.is_admin:
        flash("Las cuentas de administración no se eliminan desde aquí.", "error")
        return redirect(url_for("profiles.account"))
    form = DeleteAccountForm()
    if form.validate_on_submit():
        if current_user.check_password(form.password.data):
            user = current_user._get_current_object()
            logout_user()
            account_service.delete_account(user)
            flash("Tu cuenta y tus datos fueron eliminados. Gracias por haber usado Campo Directo.", "info")
            return redirect(url_for("main.home"))
        form.password.errors.append("Esa no es tu contraseña.")
    return render_template("profiles/account.html", form=form)


@bp.route("/vendedor/<int:user_id>/contacto")
@limiter.limit(lambda: current_app.config["CONTACT_REVEAL_RATE_LIMIT"])
def seller_contact(user_id):
    """«Ver celular» desde el perfil público: el número no va en la página del perfil."""
    seller = services.get_public_seller(user_id) or abort(404)
    response = make_response(
        render_template(
            "listings/contact.html",
            seller=seller,
            listing=None,
            back_url=url_for("profiles.public", user_id=seller.id),
            wa_link=whatsapp_url(seller.phone, f"Hola, vi tu perfil en {current_app.config['SITE_NAME']}."),
        )
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@bp.route("/vendedor/<int:user_id>/calificar", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["RATING_RATE_LIMIT"])
def rate_seller(user_id):
    seller = db.session.get(User, user_id) or abort(404)
    form = RatingForm()
    if form.validate_on_submit():
        try:
            ratings.rate_seller(seller, current_user, int(form.stars.data), form.comment.data)
            flash("¡Gracias por tu calificación!", "success")
        except ratings.RatingError as error:
            flash(str(error), "error")
    else:
        for message in form_errors(form).values():
            flash(message, "error")
    return redirect(url_for("profiles.public", user_id=seller.id) + "#calificaciones")

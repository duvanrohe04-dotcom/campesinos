from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ...constants import (
    CONTACT_SUBJECTS,
    LISTING_STATUSES,
    MESSAGE_NEW,
    RATING_HIDDEN,
    RATING_VISIBLE,
    REPORT_OPEN,
    REPORT_REASONS,
)
from ...decorators import admin_required
from ...extensions import db
from ...forms import form_errors
from ...models import (
    AttributeDef,
    Category,
    ContactMessage,
    Listing,
    Municipality,
    Rating,
    Report,
    User,
    Village,
)
from ...services import ratings
from . import bp, services
from .forms import AttributeForm, CategoryForm, CoordinatesForm, MunicipalityForm, VillageForm


def _get_or_404(model, object_id: int):
    return db.session.get(model, object_id) or abort(404)


@bp.route("/")
@admin_required
def dashboard():
    data = services.dashboard_data()
    return render_template("admin/dashboard.html", counts=data.counts, latest=data.latest)


# ---------- Usuarios ----------
@bp.route("/usuarios")
@admin_required
def users():
    text = (request.args.get("q") or "").strip()
    return render_template("admin/users.html", users=services.search_users(text), q=text)


@bp.route("/usuarios/<int:user_id>/estado", methods=["POST"])
@admin_required
def toggle_user(user_id):
    user = _get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("No puedes desactivar tu propia cuenta.", "error")
    elif user.deleted_at:
        flash("Esa cuenta fue eliminada por su dueño y no se puede reactivar.", "error")
    else:
        enabled = services.toggle_user(user)
        flash(f"Cuenta {'activada' if enabled else 'desactivada'}.", "success")
    return redirect(request.referrer or url_for("admin.users"))


@bp.route("/usuarios/<int:user_id>/verificado", methods=["POST"])
@admin_required
def toggle_verified(user_id):
    verified = services.toggle_verified_seller(_get_or_404(User, user_id))
    flash("Insignia «Vendedor verificado» otorgada." if verified else "Insignia retirada.", "success")
    return redirect(request.referrer or url_for("admin.users"))


# ---------- Calificaciones ----------
@bp.route("/calificaciones")
@admin_required
def ratings_list():
    status = request.args.get("estado", RATING_VISIBLE)
    return render_template("admin/ratings.html", ratings=ratings.list_for_moderation(status), status=status)


@bp.route("/calificaciones/<int:rating_id>/<action>", methods=["POST"])
@admin_required
def rating_action(rating_id, action):
    if action not in ("ocultar", "mostrar"):
        abort(404)
    ratings.set_visibility(_get_or_404(Rating, rating_id), visible=action == "mostrar")
    flash("Calificación actualizada.", "success")
    return redirect(url_for("admin.ratings_list", estado=RATING_VISIBLE if action == "ocultar" else RATING_HIDDEN))


# ---------- Anuncios ----------
@bp.route("/anuncios")
@admin_required
def listings():
    status = request.args.get("estado", "")
    status = status if status in LISTING_STATUSES else ""
    return render_template("admin/listings.html", listings=services.list_listings(status), status=status)


@bp.route("/anuncios/<int:listing_id>/<action>", methods=["POST"])
@admin_required
def listing_action(listing_id, action):
    listing = _get_or_404(Listing, listing_id)
    try:
        flash(services.moderate_listing(listing, action), "success")
    except ValueError:
        abort(404)
    return redirect(request.referrer or url_for("admin.listings"))


# ---------- Reportes ----------
@bp.route("/reportes")
@admin_required
def reports():
    status = request.args.get("estado", REPORT_OPEN)
    return render_template(
        "admin/reports.html", reports=services.list_reports(status), status=status, reasons=REPORT_REASONS
    )


@bp.route("/reportes/<int:report_id>/<action>", methods=["POST"])
@admin_required
def report_action(report_id, action):
    report = _get_or_404(Report, report_id)
    try:
        message = services.resolve_report(report, action)
    except ValueError:
        abort(404)
    if message:
        flash(message, "success")
    return redirect(url_for("admin.reports"))


# ---------- Mensajes de contacto ----------
@bp.route("/mensajes")
@admin_required
def messages():
    status = request.args.get("estado", MESSAGE_NEW)
    return render_template(
        "admin/messages.html", messages=services.list_messages(status), status=status, subjects=CONTACT_SUBJECTS
    )


@bp.route("/mensajes/<int:message_id>/leido", methods=["POST"])
@admin_required
def message_read(message_id):
    services.mark_message_read(_get_or_404(ContactMessage, message_id))
    return redirect(url_for("admin.messages"))


# ---------- Categorías ----------
@bp.route("/categorias")
@admin_required
def categories():
    return render_template("admin/categories.html", roots=Category.all_roots())


def _category_form_view(category: Category | None, parent: Category | None):
    form = CategoryForm(category=category, data=services.category_form_defaults(category) if category else None)
    if form.validate_on_submit():
        services.save_category(form, category, parent)
        flash("Guardado.", "success")
        return redirect(url_for("admin.categories"))
    is_root = (category and not category.parent_id) or (not category and not parent)
    return render_template("admin/category_form.html", form=form, category=category, parent=parent, is_root=is_root)


@bp.route("/categorias/nueva", methods=["GET", "POST"])
@admin_required
def category_new():
    parent_id = request.args.get("padre", "")
    parent = db.session.get(Category, int(parent_id)) if parent_id.isdigit() else None
    return _category_form_view(None, parent)


@bp.route("/categorias/<int:category_id>/editar", methods=["GET", "POST"])
@admin_required
def category_edit(category_id):
    return _category_form_view(_get_or_404(Category, category_id), None)


@bp.route("/categorias/<int:category_id>/eliminar", methods=["POST"])
@admin_required
def category_delete(category_id):
    if services.delete_category(_get_or_404(Category, category_id)):
        flash("Categoría eliminada.", "success")
    else:
        flash("No se puede eliminar: tiene subcategorías o publicaciones. Desactívala mejor.", "error")
    return redirect(url_for("admin.categories"))


# ---------- Atributos ----------
@bp.route("/categorias/<int:category_id>/atributos")
@admin_required
def attributes(category_id):
    return render_template("admin/attributes.html", category=_get_or_404(Category, category_id))


def _attribute_form_view(category: Category, attr: AttributeDef | None):
    form = AttributeForm(category=category, attr=attr, data=services.attribute_form_defaults(attr) if attr else None)
    if form.validate_on_submit():
        services.save_attribute(form, category, attr)
        flash("Guardado.", "success")
        return redirect(url_for("admin.attributes", category_id=category.id))
    return render_template("admin/attribute_form.html", form=form, category=category, attr=attr)


@bp.route("/categorias/<int:category_id>/atributos/nuevo", methods=["GET", "POST"])
@admin_required
def attribute_new(category_id):
    return _attribute_form_view(_get_or_404(Category, category_id), None)


@bp.route("/atributos/<int:attr_id>/editar", methods=["GET", "POST"])
@admin_required
def attribute_edit(attr_id):
    attr = _get_or_404(AttributeDef, attr_id)
    return _attribute_form_view(attr.category, attr)


@bp.route("/atributos/<int:attr_id>/eliminar", methods=["POST"])
@admin_required
def attribute_delete(attr_id):
    attr = _get_or_404(AttributeDef, attr_id)
    category_id = attr.category_id
    db.session.delete(attr)
    db.session.commit()
    flash("Dato eliminado (los anuncios antiguos conservan su valor guardado).", "success")
    return redirect(url_for("admin.attributes", category_id=category_id))


# ---------- Municipios y veredas ----------
@bp.route("/municipios", methods=["GET", "POST"])
@admin_required
def municipalities():
    form = MunicipalityForm()
    if form.validate_on_submit():
        created = services.add_municipality(form.name.data, form.department.data)
        flash("Municipio agregado." if created else "Ese municipio ya existe.", "success" if created else "error")
        return redirect(url_for("admin.municipalities"))
    for message in form_errors(form).values():
        flash(message, "error")
    return render_template("admin/municipalities.html", rows=services.municipalities_with_counts(), form=form)


@bp.route("/municipios/<int:mun_id>", methods=["GET", "POST"])
@admin_required
def municipality(mun_id):
    mun = _get_or_404(Municipality, mun_id)
    form = VillageForm()
    if form.validate_on_submit():
        if services.add_village(mun, form.name.data):
            flash("Vereda agregada.", "success")
        return redirect(url_for("admin.municipality", mun_id=mun.id))
    return render_template("admin/municipality.html", mun=mun, form=form)


@bp.route("/municipios/<int:mun_id>/ubicacion", methods=["POST"])
@admin_required
def municipality_location(mun_id):
    mun = _get_or_404(Municipality, mun_id)
    form = CoordinatesForm()
    if form.validate_on_submit():
        services.set_center(mun, form.point)
        flash("Ubicación guardada.", "success")
    else:
        for message in form_errors(form).values():
            flash(message, "error")
    return redirect(url_for("admin.municipality", mun_id=mun.id))


@bp.route("/veredas/<int:village_id>/ubicacion", methods=["POST"])
@admin_required
def village_location(village_id):
    village = _get_or_404(Village, village_id)
    form = CoordinatesForm()
    if form.validate_on_submit():
        services.set_center(village, form.point)
        flash("Ubicación guardada.", "success")
    else:
        for message in form_errors(form).values():
            flash(message, "error")
    return redirect(url_for("admin.municipality", mun_id=village.municipality_id))


@bp.route("/veredas/<int:village_id>/eliminar", methods=["POST"])
@admin_required
def village_delete(village_id):
    village = _get_or_404(Village, village_id)
    municipality_id = village.municipality_id
    if services.delete_village(village):
        flash("Vereda eliminada.", "success")
    else:
        flash("Esa vereda está en uso; no se puede eliminar.", "error")
    return redirect(url_for("admin.municipality", mun_id=municipality_id))

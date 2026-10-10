from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ...extensions import db
from ...models import Notification, SavedSearch
from ...services import notifications, saved_searches
from ...utils import is_safe_next
from . import bp, services
from .forms import SaveSearchForm


@bp.route("/busquedas-guardadas")
@login_required
def saved():
    return render_template("alerts/saved_searches.html", searches=services.user_searches(current_user))


@bp.route("/busquedas-guardadas/guardar", methods=["POST"])
@login_required
def save():
    form = SaveSearchForm()
    if form.validate_on_submit():
        try:
            services.save_from_form(current_user, form.query.data)
            flash("¡Listo! Te avisaremos cuando haya anuncios nuevos como estos.", "success")
        except saved_searches.SavedSearchError as error:
            flash(str(error), "error")
            return redirect(url_for("listings.index") + "?" + (form.query.data or ""))
    return redirect(url_for("alerts.saved"))


@bp.route("/busquedas-guardadas/<int:search_id>/eliminar", methods=["POST"])
@login_required
def delete(search_id):
    saved_search = db.session.get(SavedSearch, search_id) or abort(404)
    if saved_search.user_id != current_user.id:
        abort(403)
    saved_searches.delete_search(saved_search)
    flash("Búsqueda borrada.", "info")
    return redirect(url_for("alerts.saved"))


@bp.route("/notificaciones")
@login_required
def center():
    return render_template("alerts/notifications.html", items=services.notification_center(current_user))


@bp.route("/notificaciones/<int:notification_id>/abrir")
@login_required
def open_notification(notification_id):
    notification = db.session.get(Notification, notification_id) or abort(404)
    if notification.user_id != current_user.id:
        abort(403)
    notifications.mark_read(notification)
    target = notification.url
    return redirect(target if is_safe_next(target) else url_for("alerts.center"))


@bp.route("/notificaciones/leer-todas", methods=["POST"])
@login_required
def read_all():
    notifications.mark_all_read(current_user)
    return redirect(url_for("alerts.center"))

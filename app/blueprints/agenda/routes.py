from flask import Response, abort, redirect, render_template, request

from ...constants import EVENT_KINDS
from ...templating import event_url
from . import bp, services


@bp.route("/agenda")
def index():
    page = services.agenda_page(request.args.get("mes"), request.args.get("tipo"))
    return render_template("agenda/index.html", page=page, kinds=EVENT_KINDS)


@bp.route("/agenda/<slug_id>")
def detail(slug_id):
    try:
        event_id = int(slug_id.rsplit("-", 1)[-1])
    except ValueError:
        abort(404)
    event = services.get_published_event(event_id)
    if not event:
        abort(404)
    if request.path != event_url(event):  # URL canónica
        return redirect(event_url(event), code=301)
    return render_template("agenda/detail.html", event=event, kinds=EVENT_KINDS)


@bp.route("/agenda/<int:event_id>/calendario.ics")
def calendar_file(event_id):
    """Descarga el evento para agregarlo al calendario del celular."""
    event = services.get_published_event(event_id)
    if not event:
        abort(404)
    response = Response(services.ics_for(event), mimetype="text/calendar")
    response.headers["Content-Disposition"] = f'attachment; filename="evento-{event.id}.ics"'
    return response

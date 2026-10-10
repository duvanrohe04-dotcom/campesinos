from flask import (
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from ...constants import CLICK_CALL, CLICK_WHATSAPP, STATUS_REMOVED
from ...extensions import db, limiter
from ...models import Category, Listing, Municipality
from ...services import geo, posters, ratings
from ...services.attributes import display_attrs
from ...services.search import SORTS, search
from ...templating import listing_url
from ...utils import is_safe_next
from . import bp, services
from .forms import ReportForm


@bp.route("/anuncios")
def index():
    args = request.args.to_dict()
    query, info = search(args)
    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=current_app.config["PER_PAGE"], error_out=False)
    municipality = db.session.get(Municipality, int(args["mun"])) if (args.get("mun") or "").isdigit() else None
    clean_args = {k: v for k, v in args.items() if k != "page" and v}
    return render_template(
        "listings/index.html",
        page_obj=pagination,
        listings=pagination.items,
        info=info,
        chips=services.filter_chip_links(info, clean_args),
        roots=Category.active_roots(),
        args=args,
        sorts=SORTS,
        municipality=municipality,
        villages=municipality.villages if municipality else [],
        clean_args=clean_args,
    )


@bp.route("/anuncios/mapa")
def map_view():
    """Mismo listado, pero sobre un mapa. Usa los mismos filtros de la URL."""
    args = request.args.to_dict()
    _, info = search(args)
    clean_args = {k: v for k, v in args.items() if k != "page" and v}
    return render_template(
        "listings/map.html",
        info=info,
        chips=services.filter_chip_links(info, clean_args, "listings.map_view"),
        clean_args=clean_args,
        center=current_app.config["MAP_DEFAULT_CENTER"],
    )


@bp.route("/anuncios/mapa.json")
def map_data():
    query, _ = search(request.args.to_dict())
    return jsonify(points=services.map_points(query))


@bp.route("/<cat>/<sub>/<slug_id>")
def detail(cat, sub, slug_id):
    try:
        listing_id = int(slug_id.rsplit("-", 1)[-1])
    except ValueError:
        abort(404)
    listing = services.get_listing(listing_id)
    if not listing or listing.status == STATUS_REMOVED:
        abort(404)
    if not services.can_view(listing):  # pausado o vencido: el enlace de WhatsApp no debe parecer un error
        return (
            render_template(
                "listings/unavailable.html", similar=services.similar_listings(listing), category=listing.category
            ),
            410,
        )
    canonical = listing_url(listing)
    if request.path != canonical:  # URL amigable canónica
        return redirect(canonical, code=301)
    services.register_view(listing)
    map_point, map_exact = geo.listing_point(listing)
    return render_template(
        "listings/detail.html",
        l=listing,
        attrs=display_attrs(listing),
        similar=services.similar_listings(listing),
        is_fav=services.is_favorite(listing),
        is_owner=services.is_owner(listing),
        reputation=ratings.reputation(listing.user),
        map_point=map_point,
        map_exact=map_exact,
    )


def _shareable_listing(listing_id: int) -> Listing:
    """Anuncio al que se le puede generar cartel/imagen. Llevan el celular, así que solo su dueño o un admin."""
    listing = services.get_listing(listing_id)
    if not listing or not (services.is_owner(listing) or (current_user.is_authenticated and current_user.is_admin)):
        abort(404)
    return listing


def _download(data: bytes, mimetype: str, filename: str) -> Response:
    response = Response(data, mimetype=mimetype)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "private, max-age=300"
    return response


@bp.route("/anuncio/<int:listing_id>/cartel.pdf")
@limiter.limit(lambda: current_app.config["POSTER_RATE_LIMIT"])
def poster_pdf(listing_id):
    """Cartel tamaño carta con foto, precio, celular y QR, listo para imprimir."""
    listing = _shareable_listing(listing_id)
    pdf = posters.build_poster_pdf(listing, listing_url(listing, external=True))
    return _download(pdf, "application/pdf", f"cartel-{listing.slug}.pdf")


@bp.route("/anuncio/<int:listing_id>/estado.png")
@limiter.limit(lambda: current_app.config["POSTER_RATE_LIMIT"])
def status_image(listing_id):
    """Imagen cuadrada 1080×1080 para estados de WhatsApp o Facebook."""
    listing = _shareable_listing(listing_id)
    png = posters.build_status_image(listing, listing_url(listing, external=True))
    return _download(png, "image/png", f"estado-{listing.slug}.png")


def _contactable_listing(listing_id: int) -> Listing:
    """Anuncio activo que no es del propio usuario: el único que se puede contactar."""
    listing = services.get_listing(listing_id)
    if not listing or not listing.is_active or not listing.user.is_enabled:
        abort(404)
    return listing


def _private_response(response: Response) -> Response:
    """Los datos de contacto no se guardan en cachés ni se indexan."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@bp.route("/anuncio/<int:listing_id>/whatsapp")
@limiter.limit(lambda: current_app.config["CONTACT_REVEAL_RATE_LIMIT"])
def contact_whatsapp(listing_id):
    """Cuenta el contacto y lleva a WhatsApp con el mensaje listo. El celular no viaja en la página del anuncio."""
    listing = _contactable_listing(listing_id)
    if services.is_owner(listing):
        return redirect(listing_url(listing))
    services.record_click(listing, CLICK_WHATSAPP, session)
    return _private_response(redirect(services.whatsapp_link(listing)))


@bp.route("/anuncio/<int:listing_id>/contacto")
@limiter.limit(lambda: current_app.config["CONTACT_REVEAL_RATE_LIMIT"])
def contact_phone(listing_id):
    """«Ver celular»: muestra el número completo para llamar. Cuenta como contacto por llamada."""
    listing = _contactable_listing(listing_id)
    if services.is_owner(listing):
        return redirect(listing_url(listing))
    services.record_click(listing, CLICK_CALL, session)
    return _private_response(
        make_response(
            render_template(
                "listings/contact.html",
                seller=listing.user,
                listing=listing,
                back_url=listing_url(listing),
                wa_link=url_for("listings.contact_whatsapp", listing_id=listing.id),
            )
        )
    )


@bp.route("/favoritos")
@login_required
def favorites():
    return render_template("listings/favorites.html", listings=services.favorite_listings(current_user))


@bp.route("/favoritos/<int:listing_id>", methods=["POST"])
@login_required
def toggle_favorite(listing_id):
    listing = db.session.get(Listing, listing_id) or abort(404)
    saved = services.toggle_favorite(current_user, listing)
    flash("Guardado en tus favoritos." if saved else "Quitado de tus favoritos.", "success" if saved else "info")
    target = request.form.get("next")
    return redirect(target if is_safe_next(target) else listing_url(listing))


@bp.route("/anuncio/<int:listing_id>/reportar", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["REPORT_RATE_LIMIT"], methods=["POST"])
def report(listing_id):
    listing = db.session.get(Listing, listing_id) or abort(404)
    form = ReportForm()
    if form.validate_on_submit():
        services.create_report(listing, form.reason.data, form.detail.data)
        flash("Gracias. Revisaremos este anuncio.", "success")
        return redirect(listing_url(listing))
    return render_template("listings/report.html", l=listing, form=form)

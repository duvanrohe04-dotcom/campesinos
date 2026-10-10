from flask import (
    Response,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...decorators import admin_required
from ...extensions import db, limiter
from ...services import events
from . import bp, services
from .forms import ContactForm


@bp.route("/")
def home():
    return render_template(
        "main/home.html",
        recent=services.recent_listings(),
        animals=services.section_listings("animales"),
        table=services.section_listings("mesa"),
        next_event=events.next_event(),
    )


@bp.route("/quienes-somos")
def about():
    return render_template("main/about.html")


@bp.route("/como-funciona")
def how_it_works():
    return render_template("main/how_it_works.html")


@bp.route("/preguntas-frecuentes")
def faq():
    return render_template("main/faq.html")


@bp.route("/consejos-compra-segura")
def safety_tips():
    return render_template("main/safety_tips.html")


@bp.route("/terminos")
def terms():
    return render_template("main/terms.html")


@bp.route("/privacidad")
def privacy():
    return render_template("main/privacy.html")


@bp.route("/contacto", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["CONTACT_RATE_LIMIT"], methods=["POST"])
def contact():
    form = ContactForm()
    if request.method == "GET" and current_user.is_authenticated:
        form.name.data, form.contact.data = current_user.name, current_user.phone
    if form.validate_on_submit():
        services.save_contact_message(form)
        flash("¡Gracias! Recibimos tu mensaje y te responderemos pronto.", "success")
        return redirect(url_for("main.contact"))
    return render_template("main/contact.html", form=form)


@bp.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="icons/icon-192.png"), code=301)


# Direcciones que la gente escribe a mano: llevan a las rutas en español
URL_ALIASES = {"/login": "auth.login", "/register": "auth.register", "/ingreso": "auth.login"}
for _path, _endpoint in URL_ALIASES.items():
    bp.add_url_rule(
        _path,
        endpoint=f"alias_{_path.strip('/')}",
        view_func=lambda endpoint=_endpoint: redirect(url_for(endpoint), code=301),
    )


@bp.route("/robots.txt")
def robots():
    return Response(services.robots_txt(), mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap():
    return Response(services.sitemap_xml(), mimetype="application/xml")


@bp.route("/health")
def health():
    """Chequeo para Docker/monitoreo: responde 200 si la base de datos contesta."""
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        current_app.logger.exception("Health check: la base de datos no responde")
        return jsonify(status="error", database=False), 503
    return jsonify(status="ok", database=True)


@bp.route("/offline")
def offline():
    return render_template("main/offline.html")


@bp.route("/sw.js")
def service_worker():
    """El service worker se sirve desde la raíz para controlar todo el sitio."""
    response = send_from_directory(current_app.static_folder, "sw.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@bp.route("/estilos")
@admin_required
def styleguide():
    return render_template("main/styleguide.html")

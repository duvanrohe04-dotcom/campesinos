"""Rutas del admin para la agenda (eventos) y los consejos (artículos)."""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ...constants import ARTICLE_CATEGORIES, EVENT_KINDS
from ...decorators import admin_required
from ...extensions import db
from ...models import Article, Event, Municipality
from . import bp, content_services
from .content_forms import ArticleForm, EventForm


def _get_or_404(model, object_id: int):
    return db.session.get(model, object_id) or abort(404)


# ---------- Agenda ----------
@bp.route("/eventos")
@admin_required
def events():
    rows = Event.query.order_by(Event.starts_at.desc()).limit(200).all()
    return render_template("admin/events.html", events=rows, kinds=EVENT_KINDS)


def _event_form_view(event: Event | None):
    form = EventForm(data=content_services.event_defaults(event) if event and request.method == "GET" else None)
    form.municipality_id.choices = [(0, "Sin municipio"), *((m.id, m.name) for m in Municipality.ordered())]
    if form.validate_on_submit():
        saved, error = content_services.save_event(form, event, request.files.get("image"))
        if error:
            flash(error, "error")
        else:
            flash("Evento guardado.", "success")
            return redirect(url_for("admin.events"))
    return render_template("admin/event_form.html", form=form, event=event)


@bp.route("/eventos/nuevo", methods=["GET", "POST"])
@admin_required
def event_new():
    return _event_form_view(None)


@bp.route("/eventos/<int:event_id>/editar", methods=["GET", "POST"])
@admin_required
def event_edit(event_id):
    return _event_form_view(_get_or_404(Event, event_id))


@bp.route("/eventos/<int:event_id>/eliminar", methods=["POST"])
@admin_required
def event_delete(event_id):
    content_services.delete_event(_get_or_404(Event, event_id))
    flash("Evento eliminado.", "success")
    return redirect(url_for("admin.events"))


# ---------- Consejos (artículos) ----------
@bp.route("/articulos")
@admin_required
def articles():
    rows = Article.query.order_by(Article.published_at.desc()).limit(200).all()
    return render_template("admin/articles.html", articles=rows, categories=ARTICLE_CATEGORIES)


def _article_form_view(article: Article | None):
    form = ArticleForm(data=content_services.article_defaults(article) if article and request.method == "GET" else None)
    if form.validate_on_submit():
        saved, error = content_services.save_article(form, article, request.files.get("cover"), current_user.id)
        if error:
            flash(error, "error")
        else:
            flash("Artículo guardado.", "success")
            return redirect(url_for("admin.articles"))
    return render_template("admin/article_form.html", form=form, article=article)


@bp.route("/articulos/nuevo", methods=["GET", "POST"])
@admin_required
def article_new():
    return _article_form_view(None)


@bp.route("/articulos/<int:article_id>/editar", methods=["GET", "POST"])
@admin_required
def article_edit(article_id):
    return _article_form_view(_get_or_404(Article, article_id))


@bp.route("/articulos/<int:article_id>/eliminar", methods=["POST"])
@admin_required
def article_delete(article_id):
    content_services.delete_article(_get_or_404(Article, article_id))
    flash("Artículo eliminado.", "success")
    return redirect(url_for("admin.articles"))

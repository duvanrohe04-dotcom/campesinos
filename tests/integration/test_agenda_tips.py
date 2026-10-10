from datetime import timedelta

from app.extensions import db
from app.models import Article, Event, Municipality
from app.services import events

from ..conftest import login


def future(days=5):
    return events.local_now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days)


def add_event(**overrides):
    values = {"title": "Feria ganadera de Vélez", "kind": "feria", "starts_at": future(), "place": "Recinto ferial",
              "organizer": "Alcaldía", "municipality": Municipality.query.filter_by(slug="velez").one(),
              "description": "Venta de ganado"}  # fmt: skip
    values.update(overrides)
    event = Event(**values)
    db.session.add(event)
    db.session.commit()
    return event


# ------------------------------------------------------------------ agenda pública
def test_agenda_page_lists_events_and_calendar(client):
    event = add_event()
    html = client.get("/agenda").get_data(as_text=True)
    assert "Agenda del campo" in html and event.title in html and "Próximos eventos" in html
    assert "Lun" in html and "Mes siguiente" in html


def test_agenda_filters_by_kind_and_month(client):
    add_event(title="Subasta de terneros", kind="subasta")
    add_event(title="Feria grande", kind="feria")
    html = client.get("/agenda?tipo=subasta").get_data(as_text=True)
    assert "Subasta de terneros" in html and "Feria grande" not in html
    month = future().strftime("%Y-%m")
    assert "Subasta de terneros" in client.get(f"/agenda?mes={month}").get_data(as_text=True)
    assert client.get("/agenda?mes=nada&tipo=raro").status_code == 200


def test_event_detail_canonical_url_and_structured_data(client):
    event = add_event()
    url = f"/agenda/feria-ganadera-de-velez-{event.id}"
    html = client.get(url).get_data(as_text=True)
    assert "Agregar a mi calendario" in html and '"@type": "Event"' in html and "Organiza: Alcaldía" in html
    assert client.get(f"/agenda/otra-cosa-{event.id}").status_code == 301
    assert client.get("/agenda/no-existe-9999").status_code == 404
    assert client.get("/agenda/sin-id").status_code == 404


def test_unpublished_event_is_hidden(client):
    event = add_event(is_published=False)
    assert client.get(f"/agenda/x-{event.id}").status_code == 404
    assert client.get(f"/agenda/{event.id}/calendario.ics").status_code == 404
    assert event.title not in client.get("/agenda").get_data(as_text=True)


def test_ics_download(client):
    event = add_event()
    response = client.get(f"/agenda/{event.id}/calendario.ics")
    assert response.status_code == 200 and response.mimetype == "text/calendar"
    assert "BEGIN:VEVENT" in response.get_data(as_text=True) and "attachment" in response.headers["Content-Disposition"]


def test_home_highlights_next_event(client):
    Event.query.delete()  # los eventos de ejemplo del seed no cuentan aquí
    db.session.commit()
    assert "Próximo evento" not in client.get("/").get_data(as_text=True)
    add_event(title="Gran feria cercana", starts_at=future(2))
    add_event(title="Feria lejana", starts_at=future(20))
    html = client.get("/").get_data(as_text=True)
    assert "Próximo evento" in html and "Gran feria cercana" in html and "Feria lejana" not in html


# ------------------------------------------------------------------ admin agenda
def test_admin_creates_edits_and_deletes_event(admin):
    muni = Municipality.query.filter_by(slug="barbosa").one()
    data = {"title": "Capacitación del SENA", "kind": "capacitacion", "starts_at": future().strftime("%Y-%m-%dT%H:%M"),
            "place": "Casa de la cultura", "municipality_id": muni.id, "organizer": "SENA", "is_published": "y"}  # fmt: skip
    assert admin.post("/admin/eventos/nuevo", data=data).status_code == 302
    event = Event.query.filter_by(title="Capacitación del SENA").one()
    assert event.municipality_id == muni.id and event.kind == "capacitacion"
    assert "Capacitación del SENA" in admin.get("/admin/eventos").get_data(as_text=True)
    assert "Capacitación del SENA" in admin.get(f"/admin/eventos/{event.id}/editar").get_data(as_text=True)
    admin.post(f"/admin/eventos/{event.id}/editar", data={**data, "title": "Capacitación nueva"})
    db.session.refresh(event)
    assert event.title == "Capacitación nueva"
    admin.post(f"/admin/eventos/{event.id}/eliminar")
    assert db.session.get(Event, event.id) is None


def test_admin_event_validation(admin):
    before = Event.query.count()
    start = future()
    bad = {"title": "", "kind": "feria", "starts_at": start.strftime("%Y-%m-%dT%H:%M")}
    assert "Escribe el nombre" in admin.post("/admin/eventos/nuevo", data=bad).get_data(as_text=True)
    reversed_dates = {"title": "X evento", "kind": "feria", "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
                      "ends_at": (start - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")}  # fmt: skip
    assert "después de empezar" in admin.post("/admin/eventos/nuevo", data=reversed_dates).get_data(as_text=True)
    assert Event.query.count() == before


def test_agenda_admin_requires_admin(seller):
    for path in ("/admin/eventos", "/admin/eventos/nuevo", "/admin/articulos", "/admin/articulos/nuevo"):
        assert seller.get(path).status_code == 403


# ------------------------------------------------------------------ consejos
def test_seed_has_five_articles_and_index_lists_them(client):
    assert Article.query.filter_by(is_published=True).count() == 5
    html = client.get("/consejos").get_data(as_text=True)
    assert "cómo tomar buenas fotos".lower() in html.lower() and "Guía sanitaria del ICA" in html
    assert "Ganadería" in html and "min de lectura" in html


def test_tips_filter_by_category(client):
    html = client.get("/consejos?categoria=ganaderia").get_data(as_text=True)
    assert "Guía sanitaria del ICA" in html and "Cómo fijar el precio" not in html
    assert client.get("/consejos?categoria=rara").status_code == 200


def test_tip_detail_related_cta_and_seo(client):
    article = Article.query.filter_by(category="ganaderia").one()
    html = client.get(f"/consejos/{article.slug}").get_data(as_text=True)
    assert article.title in html and "Te puede interesar" in html and '"@type": "Article"' in html
    assert "Escuchar este consejo" in html and "Ver anuncios" in html and "/anuncios?cat=bovinos" in html
    assert client.get("/consejos/no-existe").status_code == 404


def test_unpublished_article_is_404(client):
    article = Article.query.first()
    article.is_published = False
    db.session.commit()
    assert client.get(f"/consejos/{article.slug}").status_code == 404
    assert article.title not in client.get("/consejos").get_data(as_text=True)


def test_admin_article_crud_sanitizes_html(admin):
    body = "<h1>Paso 1</h1><p>Riega <script>alert(1)</script><strong>temprano</strong></p>"
    data = {"title": "Cuidado del pasto", "category": "ganaderia", "summary": "Cómo cuidar el pasto de corte",
            "body": body, "is_published": "y"}  # fmt: skip
    assert admin.post("/admin/articulos/nuevo", data=data).status_code == 302
    article = Article.query.filter_by(title="Cuidado del pasto").one()
    assert "<script" not in article.body_html and "<h2>Paso 1</h2>" in article.body_html
    assert article.reading_minutes >= 1 and article.author_id
    page = admin.get(f"/consejos/{article.slug}").get_data(as_text=True)
    assert "<script>alert(1)" not in page and "<strong>temprano</strong>" in page
    assert "trix" in admin.get(f"/admin/articulos/{article.id}/editar").get_data(as_text=True).lower()
    admin.post(f"/admin/articulos/{article.id}/editar", data={**data, "title": "Pasto de corte", "is_published": ""})
    db.session.refresh(article)
    assert article.title == "Pasto de corte" and not article.is_published
    assert article.slug == "cuidado-del-pasto"  # el enlace compartido no cambia al editar el título
    admin.post(f"/admin/articulos/{article.id}/eliminar")
    assert db.session.get(Article, article.id) is None


def test_admin_article_requires_summary_and_body(admin):
    html = admin.post("/admin/articulos/nuevo", data={"title": "Sin cuerpo", "category": "ventas"}).get_data(
        as_text=True
    )
    assert "resumen corto" in html and "contenido del artículo" in html


def test_sitemap_and_footer_include_new_sections(client):
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/consejos/" in sitemap and "/agenda" in sitemap and "/precios" in sitemap
    footer = client.get("/").get_data(as_text=True)
    assert 'href="/agenda"' in footer and 'href="/consejos"' in footer
    login(client, "3000000000", "admin12345")
    assert "Agenda" in client.get("/admin/").get_data(as_text=True)

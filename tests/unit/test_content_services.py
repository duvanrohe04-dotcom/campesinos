from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Article, Event
from app.services import articles, events
from app.utils import utcnow


def make_event(**overrides):
    values = {"title": "Feria de prueba", "kind": "feria", "starts_at": events.local_now() + timedelta(days=3)}
    values.update(overrides)
    event = Event(**values)
    db.session.add(event)
    db.session.commit()
    return event


# ---------------------------------------------------------------- sanitización
def test_sanitize_removes_scripts_events_and_dangerous_links():
    dirty = (
        '<p onclick="x()">Hola <script>alert(1)</script><img src=x onerror=alert(1)>'
        '<a href="javascript:alert(1)">malo</a> <a href="https://campo.example">bueno</a></p>'
        "<style>body{display:none}</style><iframe src=//evil></iframe>"
    )
    clean = articles.sanitize_html(dirty)
    for forbidden in ("script", "onclick", "onerror", "javascript:", "iframe", "<style", "<img"):
        assert forbidden not in clean
    assert 'href="https://campo.example"' in clean and "noopener" in clean and "Hola" in clean


def test_sanitize_keeps_basic_formatting_and_maps_h1_to_h2():
    html = (
        "<h1>Título</h1><p><strong>negrita</strong> y <em>cursiva</em></p>"
        "<ul><li>uno</li></ul><blockquote>cita</blockquote>"
    )
    clean = articles.sanitize_html(html)
    assert "<h2>Título</h2>" in clean and "<h1>" not in clean
    assert "<strong>negrita</strong>" in clean and "<li>uno</li>" in clean and "<blockquote>" in clean


def test_reading_time_has_minimum_of_one_minute():
    assert articles.reading_minutes("<p>corto</p>") == 1
    assert articles.reading_minutes("<p>" + "palabra " * 540 + "</p>") == 3


def test_unique_slug_adds_suffix(app):
    first = articles.save_article(None, title="Mi consejo", summary="r", body="<p>x</p>", category="ventas",
                                  is_published=True)  # fmt: skip
    second = articles.save_article(None, title="Mi consejo", summary="r", body="<p>x</p>", category="ventas",
                                   is_published=True)  # fmt: skip
    assert first.slug == "mi-consejo" and second.slug == "mi-consejo-2"
    edited = articles.save_article(first, title="Mi consejo renombrado", summary="otro", body="<p>y</p>",
                                   category="ventas", is_published=True)  # fmt: skip
    assert edited.slug == "mi-consejo" and edited.summary == "otro"  # el slug no cambia al editar


def test_related_prefers_same_category_then_completes(app):
    base = Article.query.filter_by(category="ganaderia").first()
    related = articles.related(base, limit=3)
    assert len(related) == 3 and base.id not in {a.id for a in related}


def test_listing_category_for_article(app):
    ganaderia = Article.query.filter_by(category="ganaderia").first()
    assert articles.listing_category_for(ganaderia).slug == "bovinos"
    ventas = Article.query.filter_by(category="ventas").first()
    assert articles.listing_category_for(ventas) is None


# ---------------------------------------------------------------- agenda
def test_upcoming_hides_past_unpublished_and_orders_by_date(app):
    far = make_event(title="Lejos", starts_at=events.local_now() + timedelta(days=30))
    near = make_event(title="Cerca", starts_at=events.local_now() + timedelta(days=1))
    make_event(title="Ayer", starts_at=events.local_now() - timedelta(days=1))
    make_event(title="Oculto", is_published=False)
    ongoing = make_event(title="En curso", starts_at=events.local_now() - timedelta(days=1),
                         ends_at=events.local_now() + timedelta(days=1))  # fmt: skip
    titles = [e.title for e in events.upcoming(50)]
    assert "Ayer" not in titles and "Oculto" not in titles
    assert titles.index("En curso") < titles.index("Lejos") and titles.index("Cerca") < titles.index("Lejos")
    assert {far.id, near.id, ongoing.id} <= {e.id for e in events.upcoming(50)}
    assert events.upcoming(50, "subasta") == []


def test_parse_month_and_navigation(app):
    assert events.parse_month("2026-10") == (2026, 10)
    assert events.parse_month("basura") == (events.local_now().year, events.local_now().month)
    assert events.parse_month("2026-13")[1] == events.local_now().month
    view = events.month_view(2026, 12)
    assert view.previous == "2026-11" and view.following == "2027-01" and view.title == "Diciembre de 2026"
    assert events.month_view(2026, 1).previous == "2025-12"


def test_month_view_places_multi_day_events_on_each_day(app):
    start = events.local_now().replace(day=10, hour=8, minute=0, second=0, microsecond=0)
    make_event(title="Tres días", starts_at=start, ends_at=start + timedelta(days=2, hours=4))
    view = events.month_view(start.year, start.month)
    days = sorted(day for day, evs in view.events_by_day.items() if any(e.title == "Tres días" for e in evs))
    assert [d.day for d in days] == [10, 11, 12]
    assert not events.month_view(start.year, start.month, "subasta").events_by_day


def test_ics_content_is_valid_escaped_and_folded(app):
    event = make_event(
        title="Feria; con, símbolos", place="Recinto ferial", organizer="ICA",
        description="Línea 1\nLínea 2 " + "muy larga " * 20,
        starts_at=utcnow().replace(year=2026, month=11, day=5, hour=8, minute=30, second=0, microsecond=0),
    )  # fmt: skip
    ics = events.build_ics(event, "https://campo.example/agenda/x-1", "campo.example", "Campo Directo")
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert "DTSTART:20261105T083000" in ics and "DTEND:20261105T103000" in ics
    assert "SUMMARY:Feria\\; con\\, símbolos" in ics and "UID:evento-" in ics
    assert all(len(line.encode("utf-8")) <= 75 for line in ics.split("\r\n"))
    assert "\r\n " in ics  # hubo líneas plegadas


@pytest.mark.parametrize("raw", ["", None])
def test_parse_month_empty(raw):
    assert events.parse_month(raw) == (events.local_now().year, events.local_now().month)

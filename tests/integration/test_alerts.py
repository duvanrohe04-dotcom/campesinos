from datetime import timedelta

from app.extensions import db
from app.models import Category, Listing, Municipality, Notification, SavedSearch, User
from app.services import notifications, saved_searches
from app.utils import utcnow

from ..conftest import login

BUYER = "3134445566"


def velez_id():
    return Municipality.query.filter_by(slug="velez").one().id


def new_listing(owner_phone="3101112233", **overrides):
    values = {
        "user": User.by_phone(owner_phone),
        "category": Category.sub_by_slug("cerdos-de-engorde"),
        "ad_type": "vendo",
        "title": "Cerdos de engorde nuevos",
        "price": 700000,
        "price_unit": "animal",
        "attrs": {"peso": 90},
        "municipality_id": velez_id(),
        "created_at": utcnow(),
    }
    values.update(overrides)
    listing = Listing(**values)
    listing.set_expiry()
    db.session.add(listing)
    db.session.commit()
    return listing


def test_clean_filters_and_describe(app):
    filters = saved_searches.clean_filters(
        {"sub": "cerdos-de-engorde", "pmax": "800000", "page": "2", "orden": "x", "q": ""}
    )
    assert filters == {"sub": "cerdos-de-engorde", "pmax": "800000"}
    assert "Cerdos de engorde" in saved_searches.describe(filters) and "800.000" in saved_searches.describe(filters)


def test_save_search_from_listing_page(client):
    login(client, BUYER)
    query = f"sub=cerdos-de-engorde&mun={velez_id()}&pmax=800000&page=3"
    client.post("/busquedas-guardadas/guardar", data={"query": query})
    client.post("/busquedas-guardadas/guardar", data={"query": query})  # no se duplica
    saved = SavedSearch.query.all()
    assert len(saved) == 1 and saved[0].filters["pmax"] == "800000" and "page" not in saved[0].filters
    assert "Cerdos de engorde" in client.get("/busquedas-guardadas").get_data(as_text=True)
    assert "Avisarme de anuncios nuevos" in client.get("/anuncios?cat=bovinos").get_data(as_text=True)


def test_cannot_save_empty_search_or_exceed_limit(client):
    login(client, BUYER)
    empty = client.post("/busquedas-guardadas/guardar", data={"query": "orden=recientes"}, follow_redirects=True)
    assert "Elige al menos un filtro" in empty.get_data(as_text=True) and SavedSearch.query.count() == 0
    user = User.by_phone(BUYER)
    for i in range(20):
        db.session.add(SavedSearch(user_id=user.id, name=f"b{i}", filters={"q": f"x{i}"}))
    db.session.commit()
    over = client.post("/busquedas-guardadas/guardar", data={"query": "q=otra"}, follow_redirects=True)
    assert "hasta 20" in over.get_data(as_text=True) and SavedSearch.query.count() == 20


def test_run_creates_notifications_only_for_new_matching_listings(client):
    login(client, BUYER)
    client.post("/busquedas-guardadas/guardar", data={"query": f"sub=cerdos-de-engorde&mun={velez_id()}&pmax=800000"})
    saved = SavedSearch.query.one()
    saved.last_checked_at = utcnow() - timedelta(hours=1)
    db.session.commit()

    match = new_listing(title="Cerdos de engorde en Vélez", price=700000)
    new_listing(title="Cerdos muy caros", price=900000)  # fuera de precio
    new_listing(title="Cerdos en Barbosa", municipality_id=Municipality.query.filter_by(slug="barbosa").one().id)
    old = new_listing(title="Cerdos viejos", created_at=utcnow() - timedelta(days=3))

    assert saved_searches.run_saved_searches() == 1
    notification = Notification.query.one()
    assert notification.listing_id == match.id and notification.user_id == User.by_phone(BUYER).id
    assert old.id != notification.listing_id
    assert saved_searches.run_saved_searches() == 0  # segunda ejecución: nada nuevo


def test_own_listing_does_not_notify_owner(client):
    owner = User.by_phone("3101112233")
    db.session.add(
        SavedSearch(
            user_id=owner.id,
            name="mis cerdos",
            filters={"sub": "cerdos-de-engorde"},
            last_checked_at=utcnow() - timedelta(hours=1),
        )
    )
    db.session.commit()
    new_listing()
    assert saved_searches.run_saved_searches() == 0


def test_notification_center_counter_and_read(client):
    login(client, BUYER)
    user = User.by_phone(BUYER)
    listing = Listing.query.first()
    notifications.notify(user, "search_match", "Nuevo: Cerdos", "Coincide", "/anuncios", listing_id=listing.id)
    assert notifications.notify(user, "search_match", "Nuevo: Cerdos", listing_id=listing.id) is None  # sin duplicados
    html = client.get("/").get_data(as_text=True)
    assert "1 sin leer" in html
    center = client.get("/notificaciones").get_data(as_text=True)
    assert "Nuevo: Cerdos" in center and "Marcar todas como leídas" in center
    notification = Notification.query.one()
    response = client.get(f"/notificaciones/{notification.id}/abrir")
    assert response.status_code == 302 and response.headers["Location"].endswith("/anuncios")
    assert notifications.unread_count(user) == 0 and "sin leer" not in client.get("/").get_data(as_text=True)


def test_cannot_open_or_delete_other_users_items(client):
    other = User.by_phone("3101112233")
    notification = notifications.notify(other, "search_match", "Privado")
    saved = SavedSearch(user_id=other.id, name="x", filters={"q": "x"})
    db.session.add(saved)
    db.session.commit()
    login(client, BUYER)
    assert client.get(f"/notificaciones/{notification.id}/abrir").status_code == 403
    assert client.post(f"/busquedas-guardadas/{saved.id}/eliminar").status_code == 403
    assert db.session.get(SavedSearch, saved.id) is not None


def test_mark_all_read_and_delete_search(client):
    login(client, BUYER)
    user = User.by_phone(BUYER)
    notifications.notify(user, "search_match", "A", listing_id=1)
    notifications.notify(user, "search_match", "B", listing_id=2)
    client.post("/notificaciones/leer-todas")
    assert notifications.unread_count(user) == 0
    saved = SavedSearch(user_id=user.id, name="x", filters={"q": "x"})
    db.session.add(saved)
    db.session.commit()
    client.post(f"/busquedas-guardadas/{saved.id}/eliminar")
    assert db.session.get(SavedSearch, saved.id) is None


def test_cli_command_and_channels(app):
    from app.services.notifications import CHANNELS

    assert {"in_app", "whatsapp", "email"} <= set(CHANNELS)
    result = app.test_cli_runner().invoke(args=["check-saved-searches"])
    assert "Avisos creados: 0" in result.output


def test_alert_pages_require_login(client):
    for path in ("/notificaciones", "/busquedas-guardadas"):
        assert client.get(path).status_code == 302

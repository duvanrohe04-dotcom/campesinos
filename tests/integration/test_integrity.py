"""Integridad de datos: borrar un anuncio o una búsqueda guardada no deja avisos huérfanos ni falla en PostgreSQL."""

from sqlalchemy import text

from app.extensions import db
from app.models import Listing, Notification, SavedSearch, User

from ..conftest import login


def test_tests_run_with_foreign_keys_enforced(app):
    assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def _alert_for(listing: Listing, buyer: User) -> tuple[Notification, SavedSearch]:
    search = SavedSearch(user_id=buyer.id, name="Novillos", filters={"q": "novillo"})
    db.session.add(search)
    db.session.flush()
    note = Notification(user_id=buyer.id, kind="search_match", title="Nuevo", listing_id=listing.id)
    note.saved_search_id = search.id
    db.session.add(note)
    db.session.commit()
    return note, search


def test_owner_can_delete_a_listing_that_triggered_alerts(seller):
    buyer = User.by_phone("3134445566")
    listing = Listing.query.filter_by(user_id=User.by_phone("3101112233").id).first()
    _alert_for(listing, buyer)
    listing_id = listing.id

    response = seller.post(f"/panel/anuncio/{listing_id}/eliminar")
    assert response.status_code == 302
    assert db.session.get(Listing, listing_id) is None
    assert Notification.query.filter_by(listing_id=listing_id).count() == 0


def test_admin_can_delete_a_listing_that_triggered_alerts(admin):
    buyer = User.by_phone("3134445566")
    listing = Listing.query.first()
    _alert_for(listing, buyer)
    listing_id = listing.id

    assert admin.post(f"/admin/anuncios/{listing_id}/eliminar").status_code == 302
    assert Notification.query.filter_by(listing_id=listing_id).count() == 0


def test_deleting_a_saved_search_removes_its_notifications(client):
    buyer = User.by_phone("3134445566")
    listing = Listing.query.first()
    note, search = _alert_for(listing, buyer)
    search_id = search.id
    login(client, buyer.phone)

    assert client.post(f"/busquedas-guardadas/{search_id}/eliminar").status_code == 302
    assert db.session.get(SavedSearch, search_id) is None
    assert Notification.query.filter_by(saved_search_id=search_id).count() == 0

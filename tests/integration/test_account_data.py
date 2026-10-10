"""Ley 1581: descargar mis datos y eliminar mi cuenta."""

import json
import os

from app.extensions import db
from app.models import Favorite, Listing, Notification, Rating, SavedSearch, User

from ..conftest import login, png_bytes
from .test_listing_crud import TITLE, form_data

SELLER_PHONE = "3101112233"
BUYER_PHONE = "3134445566"


def delete(client, password="campo123", confirm=True):
    data = {"password": password}
    if confirm:
        data["confirm"] = "y"
    return client.post("/panel/cuenta/eliminar", data=data)


def test_account_pages_require_login(client):
    for path in ("/panel/cuenta", "/panel/cuenta/exportar"):
        assert client.get(path).status_code == 302
    assert client.post("/panel/cuenta/eliminar", data={"password": "x"}).status_code == 302


def test_export_contains_my_data_and_nobody_elses(seller):
    me = User.by_phone(SELLER_PHONE)
    response = seller.get("/panel/cuenta/exportar")
    assert response.status_code == 200 and response.mimetype == "application/json"
    assert "attachment" in response.headers["Content-Disposition"] and response.headers["Cache-Control"] == "no-store"
    data = json.loads(response.data)
    assert data["cuenta"]["celular"] == SELLER_PHONE and data["cuenta"]["nombre"] == me.name
    assert len(data["anuncios"]) == Listing.query.filter_by(user_id=me.id).count() > 0
    assert len(data["calificaciones_recibidas"]) == 2
    others = {u.phone for u in User.query.all()} - {SELLER_PHONE}
    assert not any(phone in response.get_data(as_text=True) for phone in others)


def test_delete_needs_correct_password_and_confirmation(seller):
    assert "Esa no es tu contraseña" in delete(seller, password="mala").get_data(as_text=True)
    assert "Marca la casilla" in delete(seller, confirm=False).get_data(as_text=True)
    assert (
        User.by_phone(SELLER_PHONE).is_enabled
        and Listing.query.filter_by(user_id=User.by_phone(SELLER_PHONE).id).count()
    )


def test_delete_account_erases_personal_data(seller, app):
    me = User.by_phone(SELLER_PHONE)
    me.email = "jorge@example.com"
    other = Listing.query.filter(Listing.user_id != me.id).first()
    db.session.add(Favorite(user_id=me.id, listing_id=other.id))
    db.session.add(SavedSearch(user_id=me.id, name="Mis búsquedas", filters={"q": "vaca"}))
    db.session.commit()
    seller.post(
        "/publicar", data={**form_data(), "photos": (png_bytes(), "foto.png")}, content_type="multipart/form-data"
    )
    mine = Listing.query.filter_by(title=TITLE).one()
    assert mine.images and any(f.endswith(".webp") for f in os.listdir(app.config["UPLOAD_FOLDER"]))
    my_id = me.id

    response = delete(seller)
    assert response.status_code == 302 and response.headers["Location"].endswith("/")

    gone = db.session.get(User, my_id)
    assert gone.name == "Usuario eliminado" and gone.phone == f"{my_id:010d}" and gone.deleted_at
    assert gone.email is None and gone.photo is None and gone.farm_name is None and not gone.is_enabled
    assert Listing.query.filter_by(user_id=my_id).count() == 0
    assert (
        Favorite.query.filter_by(user_id=my_id).count() == 0 and SavedSearch.query.filter_by(user_id=my_id).count() == 0
    )
    assert Rating.query.filter_by(seller_id=my_id).count() == 0
    assert not [f for f in os.listdir(app.config["UPLOAD_FOLDER"]) if f.endswith(".webp")]  # fotos borradas del disco
    assert seller.get("/panel").status_code == 302  # sesión cerrada
    assert seller.get(f"/vendedor/{my_id}").status_code == 404


def test_deleted_account_cannot_log_in_and_phone_and_email_are_free_again(client):
    me = User.by_phone(SELLER_PHONE)
    me.email = "jorge@example.com"
    db.session.commit()
    login(client, SELLER_PHONE)
    delete(client)
    assert login(client, SELLER_PHONE).status_code == 200  # no entra
    from .test_auth import REGISTER

    again = client.post("/registro", data={**REGISTER, "phone": SELLER_PHONE, "email": "jorge@example.com"})
    assert again.status_code == 302
    assert User.by_phone(SELLER_PHONE).id != me.id


def test_ratings_given_by_a_deleted_account_stay_but_anonymous(client):
    buyer = User.by_phone(BUYER_PHONE)
    given = Rating.query.filter_by(rater_id=buyer.id).count()
    assert given == 1
    original_first_name = buyer.name.split()[0]
    login(client, BUYER_PHONE)
    delete(client)
    rating = Rating.query.filter_by(rater_id=buyer.id).one()
    assert rating.rater.name == "Usuario eliminado"
    jorge = User.by_phone(SELLER_PHONE)
    page = client.get(f"/vendedor/{jorge.id}").get_data(as_text=True)
    assert 'font-bold">Usuario<' in page and BUYER_PHONE not in page and original_first_name not in page


def test_notifications_of_deleted_user_are_removed(client):
    buyer = User.by_phone(BUYER_PHONE)
    listing = Listing.query.first()
    db.session.add(Notification(user_id=buyer.id, kind="search_match", title="Nuevo", listing_id=listing.id))
    db.session.commit()
    login(client, BUYER_PHONE)
    delete(client)
    assert Notification.query.filter_by(user_id=buyer.id).count() == 0


def test_admin_user_list_has_no_dead_links_and_marks_deleted_accounts(client):
    login(client, BUYER_PHONE)
    delete(client)
    client.post("/salir")
    login(client, "3000000000", "admin12345")
    html = client.get("/admin/usuarios").get_data(as_text=True)
    assert "Eliminada por su dueño" in html
    admin = User.by_phone("3000000000")
    assert f"/vendedor/{admin.id}" not in html  # no hay botón «Perfil» hacia una cuenta de administración
    assert f"/vendedor/{User.by_phone(SELLER_PHONE).id}" in html


def test_admin_cannot_delete_their_account_here(admin):
    response = delete(admin, password="admin12345")
    assert response.status_code == 302 and response.headers["Location"].endswith("/panel/cuenta")
    assert User.by_phone("3000000000").is_enabled

import os
from datetime import timedelta

from app.extensions import db
from app.models import DailyStat, Listing, User
from app.services.stats import weekly_series
from app.utils import utcnow

from ..conftest import login, png_bytes, url_of


def listing_of(phone):
    return Listing.query.filter(Listing.user.has(User.phone == phone)).first()


def test_views_and_contacts_feed_daily_stats(client):
    listing = listing_of("3101112233")
    client.get(url_of(listing))
    client.get(f"/anuncio/{listing.id}/whatsapp")
    client.get(f"/anuncio/{listing.id}/contacto")
    row = db.session.get(DailyStat, (listing.id, utcnow().date()))
    assert (row.views, row.whatsapp, row.calls) == (1, 1, 1)


def test_weekly_series_covers_seven_days_and_ignores_old_data(app):
    owner = User.by_phone("3101112233")
    listing = listing_of("3101112233")
    today = utcnow().date()
    db.session.add_all(
        [
            DailyStat(listing_id=listing.id, day=today, views=4, whatsapp=1, calls=1),
            DailyStat(listing_id=listing.id, day=today - timedelta(days=6), views=3, whatsapp=0, calls=0),
            DailyStat(listing_id=listing.id, day=today - timedelta(days=7), views=99, whatsapp=9, calls=9),
        ]
    )
    db.session.commit()
    series = weekly_series(owner)
    assert len(series.labels) == 7 and series.views[-1] == 4 and series.views[0] == 3
    assert series.total_views == 7 and series.total_contacts == 2


def test_panel_shows_weekly_summary_chart_and_actions(seller):
    listing = listing_of("3101112233")
    db.session.add(DailyStat(listing_id=listing.id, day=utcnow().date(), views=5, whatsapp=2, calls=0))
    db.session.commit()
    html = seller.get("/panel").get_data(as_text=True)
    assert "Esta semana" in html and 'id="weekly-chart"' in html and "chart.js" in html
    for action in ("Editar", "Pausar", "Vendido", "Renovar", "Duplicar", "Eliminar"):
        assert action in html


def test_panel_warns_about_expiring_listing_and_renews(seller):
    listing = listing_of("3101112233")
    listing.expires_at = utcnow() + timedelta(days=2)
    db.session.commit()
    html = seller.get("/panel").get_data(as_text=True)
    assert "vence en" in html and "Renovar 30 días" in html
    seller.post(f"/panel/anuncio/{listing.id}/renovar")
    db.session.refresh(listing)
    assert listing.days_left >= 29


def test_profile_photo_upload_replace_and_remove(seller, app):
    user = User.by_phone("3101112233")
    data = {"name": user.name, "municipality_id": user.municipality_id, "photo": (png_bytes((800, 800)), "yo.png")}
    assert seller.post("/panel/perfil", data=data, content_type="multipart/form-data").status_code == 302
    db.session.refresh(user)
    first = user.photo
    assert (
        first
        and first in os.listdir(app.config["UPLOAD_FOLDER"])
        and user.photo_thumb in os.listdir(app.config["UPLOAD_FOLDER"])
    )
    assert user.photo_thumb in seller.get(f"/vendedor/{user.id}").get_data(as_text=True)

    data["photo"] = (png_bytes((600, 600), (200, 50, 50)), "nueva.png")
    seller.post("/panel/perfil", data=data, content_type="multipart/form-data")
    db.session.refresh(user)
    assert user.photo != first and first not in os.listdir(app.config["UPLOAD_FOLDER"])

    seller.post("/panel/perfil", data={"name": user.name, "municipality_id": user.municipality_id, "remove_photo": "y"})
    db.session.refresh(user)
    assert user.photo is None


def test_invalid_profile_photo_is_rejected(seller):
    import io

    user = User.by_phone("3101112233")
    data = {"name": user.name, "municipality_id": user.municipality_id, "photo": (io.BytesIO(b"nada"), "x.png")}
    response = seller.post("/panel/perfil", data=data, content_type="multipart/form-data")
    assert response.status_code == 200 and "No pudimos leer" in response.get_data(as_text=True)
    assert User.by_phone("3101112233").photo is None


def test_seller_only_sees_own_listings_in_panel(client):
    login(client, "3112223344")
    html = client.get("/panel").get_data(as_text=True)
    assert listing_of("3101112233").title not in html

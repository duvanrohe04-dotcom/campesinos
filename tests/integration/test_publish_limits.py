"""Anti-spam al publicar: tope de anuncios activos y límite de velocidad."""

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Listing, User
from app.services.seeding import seed_all

from ..conftest import login
from .test_listing_crud import TITLE, form_data


def active_count(user):
    return Listing.query.filter_by(user_id=user.id, status="active").count()


def test_active_listing_cap_blocks_publishing(seller, app):
    user = User.by_phone("3101112233")
    app.config["MAX_ACTIVE_LISTINGS"] = active_count(user)
    page = seller.get("/publicar", follow_redirects=True).get_data(as_text=True)
    assert "que es el máximo" in page
    assert seller.post("/publicar", data=form_data()).status_code == 302
    assert Listing.query.filter_by(title=TITLE).first() is None


def test_cap_frees_up_when_a_listing_is_sold(seller, app):
    user = User.by_phone("3101112233")
    app.config["MAX_ACTIVE_LISTINGS"] = active_count(user)
    first = Listing.query.filter_by(user_id=user.id, status="active").first()
    seller.post(f"/panel/anuncio/{first.id}/vendido")
    assert seller.post("/publicar", data=form_data()).headers["Location"].endswith("/listo")
    assert Listing.query.filter_by(title=TITLE).count() == 1


def test_new_accounts_have_a_lower_cap(seller, app):
    user = User.by_phone("3101112233")
    app.config["NEW_ACCOUNT_HOURS"] = 24  # la cuenta de prueba se creó hace segundos
    app.config["NEW_ACCOUNT_MAX_LISTINGS"] = active_count(user)
    page = seller.get("/publicar", follow_redirects=True).get_data(as_text=True)
    assert "Tu cuenta es nueva" in page


def test_old_accounts_are_not_limited_as_new(seller, app):
    from datetime import timedelta

    from app.utils import utcnow

    user = User.by_phone("3101112233")
    user.created_at = utcnow() - timedelta(days=30)
    db.session.commit()
    app.config["NEW_ACCOUNT_HOURS"] = 24
    app.config["NEW_ACCOUNT_MAX_LISTINGS"] = 1
    assert seller.get("/publicar").status_code == 200


def test_admin_is_not_limited(admin, app):
    app.config["MAX_ACTIVE_LISTINGS"] = 0
    assert admin.get("/publicar").status_code == 200


def test_publish_rate_limit_returns_friendly_429(tmp_path):
    class Config(TestingConfig):
        RATELIMIT_ENABLED = True
        PUBLISH_RATE_LIMIT = "2 per hour"
        UPLOAD_FOLDER = str(tmp_path)

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        seed_all(samples=True)
        client = app.test_client()
        login(client, "3101112233")
        statuses = [
            client.post("/publicar", data=form_data(title=f"Novillo número {i} bueno")).status_code for i in range(3)
        ]
        assert statuses[:2] == [302, 302] and statuses[2] == 429
        assert "Vas muy rápido" in client.post("/publicar", data=form_data()).get_data(as_text=True)
        db.session.remove()
        db.drop_all()

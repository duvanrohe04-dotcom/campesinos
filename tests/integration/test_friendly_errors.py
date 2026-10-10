"""Páginas que no dejan a la persona perdida: anuncio no disponible y formulario vencido."""

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Listing, User

from ..conftest import url_of


def _listing_with(status):
    listing = Listing.query.filter(Listing.title.contains("Novillo cebú"), Listing.status == "active").first()
    listing.status = status
    db.session.commit()
    return listing


def test_paused_or_expired_listing_link_explains_instead_of_404(client):
    for status in ("paused", "expired"):
        listing = _listing_with(status)
        response = client.get(url_of(listing))
        html = response.get_data(as_text=True)
        assert response.status_code == 410 and "ya no está disponible" in html
        assert listing.title not in html  # no se filtra el contenido de un anuncio que no es público
        assert "Anuncios parecidos" in html
        listing.status = "active"
        db.session.commit()


def test_removed_listing_is_a_plain_404(client):
    listing = _listing_with("removed")
    assert client.get(url_of(listing)).status_code == 404


def test_owner_still_sees_their_paused_listing(seller):
    owner = User.by_phone("3101112233")
    listing = Listing.query.filter_by(user_id=owner.id, status="active").first()
    listing.status = "paused"
    db.session.commit()
    response = seller.get(url_of(listing))
    assert response.status_code == 200 and listing.title in response.get_data(as_text=True)


def test_expired_form_goes_back_with_a_message(tmp_path):
    class Config(TestingConfig):
        WTF_CSRF_ENABLED = True
        UPLOAD_FOLDER = str(tmp_path)

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        client = app.test_client()
        response = client.post("/registro", data={"name": "x"}, headers={"Referer": "http://localhost/registro"})
        assert response.status_code == 302 and response.headers["Location"] == "/registro"
        assert "venció" in client.get("/registro").get_data(as_text=True)

        foreign = client.post("/registro", data={"name": "x"}, headers={"Referer": "http://malo.example/registro"})
        assert foreign.status_code == 400  # nunca se redirige a otro sitio
        db.drop_all()

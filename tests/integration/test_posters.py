import io

from PIL import Image

from app.extensions import db
from app.models import Listing, User
from app.services import posters

from ..conftest import login, png_bytes
from .test_listing_crud import created, form_data


def active_listing():
    return Listing.query.filter(Listing.title.contains("Novillo cebú")).first()


def test_phone_and_price_formatting():
    assert posters.format_phone("3101234567") == "310 123 4567"
    assert posters.format_phone("123") == "123"


def test_posters_carry_the_phone_so_only_the_owner_can_get_them(client):
    listing = active_listing()
    assert client.get(f"/anuncio/{listing.id}/cartel.pdf").status_code == 404
    assert client.get(f"/anuncio/{listing.id}/estado.png").status_code == 404
    login(client, "3134445566")  # otra persona con sesión: tampoco
    assert client.get(f"/anuncio/{listing.id}/cartel.pdf").status_code == 404


def test_poster_pdf_download(client):
    listing = active_listing()
    login(client, listing.user.phone)
    response = client.get(f"/anuncio/{listing.id}/cartel.pdf")
    assert response.status_code == 200 and response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF") and len(response.data) > 3000
    assert 'attachment; filename="cartel-' in response.headers["Content-Disposition"]
    assert b"/Letter" in response.data or b"612" in response.data  # tamaño carta


def test_status_image_is_1080_square_png(client):
    listing = active_listing()
    login(client, listing.user.phone)
    response = client.get(f"/anuncio/{listing.id}/estado.png")
    assert response.status_code == 200 and response.mimetype == "image/png"
    image = Image.open(io.BytesIO(response.data))
    assert image.size == (1080, 1080) and image.format == "PNG"
    assert "estado-" in response.headers["Content-Disposition"]


def test_poster_with_photo_long_title_and_agreement_price(seller):
    data = form_data(title="Novillo gordo de prueba " + "muy largo " * 5, price="", price_unit="lote")
    data["photos"] = (png_bytes((1600, 900), (20, 90, 160)), "foto.png")
    seller.post("/publicar", data={**data, "price": "1.500.000"}, content_type="multipart/form-data")
    listing = Listing.query.filter(Listing.title.contains("muy largo")).one()
    assert listing.images
    assert seller.get(f"/anuncio/{listing.id}/cartel.pdf").data.startswith(b"%PDF")
    assert Image.open(io.BytesIO(seller.get(f"/anuncio/{listing.id}/estado.png").data)).size == (1080, 1080)
    listing.price, listing.price_unit = None, "a convenir"
    db.session.commit()
    assert seller.get(f"/anuncio/{listing.id}/estado.png").status_code == 200


def test_hidden_or_unknown_listing_has_no_poster(client):
    listing = active_listing()
    listing.status = "paused"
    db.session.commit()
    assert client.get(f"/anuncio/{listing.id}/cartel.pdf").status_code == 404
    assert client.get("/anuncio/99999/estado.png").status_code == 404
    login(client, listing.user.phone)
    assert client.get(f"/anuncio/{listing.id}/cartel.pdf").status_code == 200  # el dueño sí


def test_sold_listing_poster_only_for_owner(client):
    listing = active_listing()
    listing.status = "sold"
    db.session.commit()
    assert client.get(f"/anuncio/{listing.id}/estado.png").status_code == 404


def test_download_buttons_in_detail_and_panel(seller):
    from ..conftest import url_of

    own = Listing.query.filter(Listing.user.has(User.phone == "3101112233"), Listing.status == "active").first()
    assert "Cartel para imprimir" in seller.get(url_of(own)).get_data(as_text=True)
    panel = seller.get("/panel").get_data(as_text=True)
    assert "Cartel PDF" in panel and "Imagen estado" in panel
    seller.post("/publicar", data=form_data())
    assert created()

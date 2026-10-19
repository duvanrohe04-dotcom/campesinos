import io
import os

from app.extensions import db
from app.models import Category, Listing, Municipality, User

from ..conftest import login, png_bytes

TITLE = "Novillo gordo de prueba"


def form_data(**overrides):
    data = {
        "ad_type": "vendo", "category_id": Category.sub_by_slug("novillos").id, "title": TITLE,
        "attr_sexo": "Macho", "attr_raza": "Cebú", "attr_edad": "18", "attr_edad__unit": "meses",
        "attr_peso": "320", "quantity": "2", "price": "3.200.000", "price_unit": "cabeza",
        "municipality_id": Municipality.query.filter_by(slug="velez").first().id,
    }  # fmt: skip
    data.update(overrides)
    return data


def created():
    return Listing.query.filter_by(title=TITLE).one()


def test_create_listing_with_photo(seller, app):
    data = form_data()
    data["photos"] = (png_bytes(), "foto.png")
    response = seller.post("/publicar", data=data, content_type="multipart/form-data")
    assert response.status_code == 302 and "/listo" in response.headers["Location"]
    listing = created()
    assert listing.price == 3200000 and listing.attrs["edad"] == 18 and listing.expires_at
    assert len(listing.images) == 1
    files = os.listdir(app.config["UPLOAD_FOLDER"])
    assert listing.images[0].filename in files and listing.images[0].thumb in files


def test_done_page_has_whatsapp_share(seller):
    seller.post("/publicar", data=form_data())
    html = seller.get(f"/panel/anuncio/{created().id}/listo").get_data(as_text=True)
    assert "wa.me/?text=" in html and "Compartir por WhatsApp" in html


def test_create_requires_login(client):
    assert client.get("/publicar").status_code == 302


def test_create_validation_errors(seller):
    # «Terneros» sí pregunta el sexo (en «Novillos» ya lo decide el tipo)
    data = form_data(category_id=Category.sub_by_slug("terneros").id, title="ab", price="", attr_sexo="")
    response = seller.post("/publicar", data=data)
    html = response.get_data(as_text=True)
    assert response.status_code == 200 and "5 a 80 letras" in html and "obligatorio" in html
    assert Listing.query.filter_by(title="ab").count() == 0


def test_invalid_image_rejected(seller):
    data = form_data()
    data["photos"] = (io.BytesIO(b"no soy una imagen"), "falsa.png")
    response = seller.post("/publicar", data=data, content_type="multipart/form-data")
    assert response.status_code == 200 and "No pudimos leer" in response.get_data(as_text=True)
    assert Listing.query.filter_by(title=TITLE).count() == 0


def test_any_user_can_sell_buy_and_rent(client):
    """Un usuario que se registró como comprador también puede vender; y un vendedor puede comprar."""
    login(client, "3134445566")  # cuenta de ejemplo con rol «buyer»
    assert client.post("/publicar", data=form_data(title="Novillo del comprador")).status_code == 302
    assert Listing.query.filter_by(title="Novillo del comprador", ad_type="vendo").count() == 1
    assert (
        client.post("/publicar", data=form_data(ad_type="compro", price="", title="Busco un novillo")).status_code
        == 302
    )
    client.post("/salir")
    login(client, "3101112233")  # vendedor
    assert (
        client.post("/publicar", data=form_data(ad_type="compro", price="", title="Compro abono orgánico")).status_code
        == 302
    )
    assert Listing.query.filter_by(title="Compro abono orgánico", ad_type="compro").count() == 1


def test_publish_form_offers_all_ad_types_and_prefills_from_shortcut(client):
    login(client, "3134445566")
    html = client.get("/publicar").get_data(as_text=True)
    assert all(f'value="{kind}"' in html for kind in ("vendo", "compro", "alquilo"))
    wanted = client.get("/publicar?tipo=compro").get_data(as_text=True)
    assert 'value="compro" checked' in wanted
    assert 'value="vendo" checked' not in wanted
    assert (
        "checked" not in client.get("/publicar?tipo=inventado").get_data(as_text=True).split('name="ad_type"')[1][:80]
    )


def test_panel_shows_sell_and_buy_shortcuts(client):
    login(client, "3134445566")
    html = client.get("/panel").get_data(as_text=True)
    assert "Quiero vender algo" in html and "Busco comprar algo" in html and "/publicar?tipo=compro" in html


def test_register_has_no_role_choice_and_new_user_can_publish(client):
    html = client.get("/registro").get_data(as_text=True)
    assert 'name="role"' not in html and "comprar, vender, alquilar o buscar" in html
    data = {
        "name": "Ana Ruiz",
        "phone": "3159998877",
        "password": "secreto1",
        "municipality_id": 1,
        "accept_terms": "y",
    }
    client.post("/registro", data=data)
    assert client.post("/publicar", data=form_data(title="Mi primer anuncio nuevo")).status_code == 302


def test_edit_pause_sold_renew_delete(seller):
    seller.post("/publicar", data=form_data())
    listing = created()
    response = seller.post(
        f"/panel/anuncio/{listing.id}/editar", data=form_data(title="Novillo editado listo", price="4.000.000")
    )
    assert response.status_code == 302
    db.session.refresh(listing)
    assert listing.title == "Novillo editado listo" and listing.price == 4000000
    for action, status in (("pausar", "paused"), ("vendido", "sold"), ("renovar", "active")):
        seller.post(f"/panel/anuncio/{listing.id}/{action}")
        db.session.refresh(listing)
        assert listing.status == status
    seller.post(f"/panel/anuncio/{listing.id}/eliminar")
    assert db.session.get(Listing, listing.id) is None


def test_unknown_action_is_404(seller):
    seller.post("/publicar", data=form_data())
    assert seller.post(f"/panel/anuncio/{created().id}/volar").status_code == 404


def test_cannot_edit_or_delete_others_listing(client):
    login(client, "3112223344")  # otra vendedora
    other = Listing.query.filter(Listing.user.has(User.phone == "3101112233")).first()
    assert client.get(f"/panel/anuncio/{other.id}/editar").status_code == 403
    assert client.post(f"/panel/anuncio/{other.id}/eliminar").status_code == 403
    assert client.get(f"/publicar?copiar={other.id}").status_code == 403
    assert db.session.get(Listing, other.id) is not None


def test_duplicate_prefills_form(seller):
    own = Listing.query.filter(Listing.user.has(User.phone == "3101112233")).first()
    assert own.title in seller.get(f"/publicar?copiar={own.id}").get_data(as_text=True)


def test_panel_and_profile(seller):
    assert "Mis anuncios" in seller.get("/panel").get_data(as_text=True)
    response = seller.post(
        "/panel/perfil",
        data={"name": "Jorge R.", "municipality_id": 1, "farm_name": "La Nueva", "bio": "Cultivo guayaba"},
    )
    assert response.status_code == 302
    user = User.by_phone("3101112233")
    assert user.farm_name == "La Nueva" and user.name == "Jorge R."
    assert "Escribe tu nombre" in seller.post("/panel/perfil", data={"name": "", "municipality_id": 1}).get_data(
        as_text=True
    )

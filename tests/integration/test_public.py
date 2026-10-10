from app.extensions import db
from app.models import Favorite, Listing, Report, User

from ..conftest import login, url_of


def by_title(text):
    return Listing.query.filter(Listing.title.contains(text)).first()


def test_home_and_listing_pages(client):
    assert client.get("/").status_code == 200
    html = client.get("/anuncios").get_data(as_text=True)
    assert "Novillo" in html


def test_filters_by_category_text_and_attrs(client):
    html = client.get("/anuncios?cat=bovinos").get_data(as_text=True)
    assert "Novillo" in html and "Guayaba" not in html
    html = client.get("/anuncios?q=guayaba").get_data(as_text=True)
    assert "Guayaba" in html and "Novillo" not in html
    html = client.get("/anuncios?cat=bovinos&a_sexo=Hembra").get_data(as_text=True)
    assert "Holstein" in html and "Novillo cebú" not in html
    html = client.get("/anuncios?cat=bovinos&a_peso_min=400").get_data(as_text=True)
    assert "Holstein" in html and "Novillo cebú" not in html
    html = client.get("/anuncios?cat=bovinos&a_edad_max=24").get_data(as_text=True)
    assert "Novillo cebú" in html and "Holstein" not in html


def test_price_range_order_and_chips(client):
    html = client.get("/anuncios?pmin=1000000&pmax=5000000&orden=precio_asc").get_data(as_text=True)
    assert "Novillo cebú" in html and "Guayaba" not in html
    assert "Desde $ 1.000.000" in html  # chip eliminable


def test_ad_type_filter(client):
    html = client.get("/anuncios?tipo=compro").get_data(as_text=True)
    assert "Busco terneros" in html and "Novillo cebú" not in html


def test_pagination_keeps_filters(client, app):
    app.config["PER_PAGE"] = 2
    html = client.get("/anuncios?cat=bovinos").get_data(as_text=True)
    assert "Página 1 de 2" in html and "page=2" in html and "cat=bovinos" in html


def test_detail_canonical_url_and_counters(client):
    listing = by_title("Novillo cebú")
    url = url_of(listing)
    assert url.count("/") == 3
    html = client.get(url).get_data(as_text=True)
    assert "guía sanitaria" in html
    assert listing.user.phone not in html and "wa.me" not in html and "tel:" not in html  # el celular no va en el HTML
    db.session.refresh(listing)
    assert listing.views_count == 1
    assert client.get(url.rsplit("/", 1)[0] + f"/cualquier-cosa-{listing.id}").status_code == 301

    whatsapp = client.get(f"/anuncio/{listing.id}/whatsapp")
    assert whatsapp.status_code == 302 and whatsapp.headers["Location"].startswith(
        f"https://wa.me/57{listing.user.phone}"
    )
    assert whatsapp.headers["Cache-Control"] == "no-store"
    client.get(f"/anuncio/{listing.id}/whatsapp")  # solo cuenta una vez por sesión
    reveal = client.get(f"/anuncio/{listing.id}/contacto")
    assert reveal.status_code == 200 and "noindex" in reveal.headers["X-Robots-Tag"]
    page = reveal.get_data(as_text=True)
    phone = listing.user.phone
    assert f"tel:+57{phone}" in page and f"{phone[:3]} {phone[3:6]} {phone[6:]}" in page
    db.session.refresh(listing)
    assert listing.whatsapp_clicks == 1 and listing.call_clicks == 1


def test_owner_view_and_click_are_not_counted(client):
    listing = by_title("Novillo cebú")
    login(client, listing.user.phone)
    client.get(url_of(listing))
    assert client.get(f"/anuncio/{listing.id}/whatsapp").status_code == 302
    assert client.get(f"/anuncio/{listing.id}/contacto").headers["Location"].endswith(url_of(listing))
    db.session.refresh(listing)
    assert listing.views_count == 0 and listing.whatsapp_clicks == 0 and listing.call_clicks == 0


def test_contact_routes_only_work_for_active_listings_of_enabled_sellers(client):
    listing = by_title("Novillo cebú")
    listing.status = "paused"
    db.session.commit()
    assert client.get(f"/anuncio/{listing.id}/whatsapp").status_code == 404
    assert client.get(f"/anuncio/{listing.id}/contacto").status_code == 404
    listing.status = "active"
    listing.user.is_enabled = False
    db.session.commit()
    assert client.get(f"/anuncio/{listing.id}/contacto").status_code == 404
    assert client.get("/anuncio/999999/contacto").status_code == 404


def test_old_click_beacon_endpoint_is_gone(client):
    listing = by_title("Novillo cebú")
    assert client.post(f"/anuncio/{listing.id}/clic/whatsapp").status_code in (404, 405)


def test_non_animal_has_no_ica_notice(client):
    assert 'role="note"' not in client.get(url_of(by_title("Guayaba"))).get_data(as_text=True)


def test_hidden_listing_is_404_for_public_but_visible_to_owner(client):
    listing = by_title("Novillo cebú")
    listing.status = "paused"
    db.session.commit()
    assert client.get(url_of(listing)).status_code == 410  # el enlace explica que ya no está disponible
    login(client, listing.user.phone)
    assert client.get(url_of(listing)).status_code == 200


def test_seller_profile(client):
    user = User.by_phone("3101112233")
    html = client.get(f"/vendedor/{user.id}").get_data(as_text=True)
    assert "Finca La Esperanza" in html
    admin_user = User.by_phone("3000000000")
    assert client.get(f"/vendedor/{admin_user.id}").status_code == 404


def test_favorites_flow(client):
    listing = Listing.query.first()
    assert client.post(f"/favoritos/{listing.id}").status_code == 302  # a login
    assert Favorite.query.count() == 0
    login(client, "3134445566")
    client.post(f"/favoritos/{listing.id}")
    assert Favorite.query.count() == 1
    assert listing.title in client.get("/favoritos").get_data(as_text=True)
    client.post(f"/favoritos/{listing.id}")
    assert Favorite.query.count() == 0


def test_report_listing(client):
    listing = Listing.query.first()
    response = client.post(f"/anuncio/{listing.id}/reportar", data={"reason": "fraude", "detail": "Parece estafa"})
    assert response.status_code == 302 and Report.query.count() == 1
    assert "Elige el motivo" in client.post(f"/anuncio/{listing.id}/reportar", data={}).get_data(as_text=True)


def test_error_pages_use_site_design(client):
    response = client.get("/no/existe/nada-99999")
    assert response.status_code == 404 and "No encontramos esa página" in response.get_data(as_text=True)

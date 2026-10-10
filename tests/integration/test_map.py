from app.extensions import db
from app.models import Listing, Municipality

from ..conftest import url_of
from .test_listing_crud import TITLE, created, form_data


def test_publish_stores_rounded_point_only(seller):
    seller.post("/publicar", data=form_data(lat="6.013912", lng="-73.673651"))
    listing = created()
    assert (listing.lat, listing.lng) == (6.01, -73.67)  # nunca el punto exacto


def test_point_is_optional_and_validated(seller):
    seller.post("/publicar", data=form_data())
    assert created().lat is None
    bad = seller.post("/publicar", data=form_data(title="Otro novillo bueno", lat="40.4", lng="-3.7"))
    assert bad.status_code == 200 and "debe estar en Colombia" in bad.get_data(as_text=True)
    only_one = seller.post("/publicar", data=form_data(title="Otro novillo malo", lat="6.0"))
    assert "no es válido" in only_one.get_data(as_text=True)
    assert Listing.query.filter(Listing.title.contains("Otro novillo")).count() == 0


def test_edit_keeps_and_updates_point(seller):
    seller.post("/publicar", data=form_data(lat="6.02", lng="-73.68"))
    listing = created()
    html = seller.get(f"/panel/anuncio/{listing.id}/editar").get_data(as_text=True)
    assert 'value="6.02"' in html and 'id="map-picker"' in html
    seller.post(f"/panel/anuncio/{listing.id}/editar", data=form_data(title=TITLE, lat="", lng=""))
    db.session.refresh(listing)
    assert listing.lat is None


def test_detail_shows_approximate_map_card(client):
    listing = Listing.query.filter(Listing.title.contains("Novillo cebú")).first()
    html = client.get(url_of(listing)).get_data(as_text=True)
    assert 'id="listing-map"' in html and "zona aproximada" in html and "js/map.js" in html
    assert f'data-lat="{listing.municipality.lat}"' in html  # sin punto propio: centro del municipio
    listing.lat, listing.lng = 6.02, -73.68
    db.session.commit()
    assert 'data-lat="6.02"' in client.get(url_of(listing)).get_data(as_text=True)


def test_map_page_and_json_points(client):
    page = client.get("/anuncios/mapa?cat=bovinos").get_data(as_text=True)
    assert 'id="map"' in page and "Ver como lista" in page and "aproximadas" in page
    data = client.get("/anuncios/mapa.json?cat=bovinos").get_json()
    titles = {p["title"] for p in data["points"]}
    assert titles and all("Novillo" in t or "Holstein" in t or "terneros" in t.lower() for t in titles)
    first = data["points"][0]
    assert {"id", "title", "price", "url", "lat", "lng", "exact", "place"} <= set(first)
    assert first["url"].startswith("/bovinos/") and first["price"].startswith("$")


def test_map_json_respects_filters_and_limits(client):
    all_points = client.get("/anuncios/mapa.json").get_json()["points"]
    fruit = client.get("/anuncios/mapa.json?cat=agricolas").get_json()["points"]
    assert 0 < len(fruit) < len(all_points)
    assert client.get("/anuncios/mapa.json?q=zzzz-no-existe").get_json()["points"] == []


def test_near_me_filter_on_list_and_map(client):
    velez = Municipality.query.filter_by(slug="velez").one()
    near = f"{velez.lat},{velez.lng}"
    html = client.get("/anuncios", query_string={"near": near, "radio": "5"}).get_data(as_text=True)
    assert "Cerca de mí (5 km)" in html and "Guayaba pera" in html
    assert "Novillo cebú" not in html  # Puente Nacional queda a más de 5 km
    wide = client.get("/anuncios", query_string={"near": near, "radio": "25"}).get_data(as_text=True)
    assert "Novillo cebú" in wide and "Holstein" in wide
    points = client.get("/anuncios/mapa.json", query_string={"near": near, "radio": "5"}).get_json()["points"]
    assert points and all(abs(p["lat"] - velez.lat) < 0.1 for p in points)
    map_page = client.get("/anuncios/mapa", query_string={"near": near, "radio": "10"}).get_data(as_text=True)
    assert f'data-near="{round(velez.lat, 2)},{round(velez.lng, 2)}"' in map_page


def test_near_with_garbage_is_ignored(client):
    assert client.get("/anuncios?near=hola&radio=x").status_code == 200
    assert client.get("/anuncios?near=1,2").status_code == 200  # fuera de Colombia: se ignora


def test_list_page_offers_map_and_near_buttons(client):
    html = client.get("/anuncios").get_data(as_text=True)
    assert "Ver en mapa" in html and html.count("data-near-url") >= 3


def test_admin_edits_municipality_and_village_centers(admin):
    from app.models import Village

    velez = Municipality.query.filter_by(slug="velez").one()
    admin.post(f"/admin/municipios/{velez.id}/ubicacion", data={"lat": "6.05", "lng": "-73.70"})
    db.session.refresh(velez)
    assert (velez.lat, velez.lng) == (6.05, -73.7)
    bad = admin.post(f"/admin/municipios/{velez.id}/ubicacion", data={"lat": "1", "lng": "2"}, follow_redirects=True)
    assert "Colombia" in bad.get_data(as_text=True) and velez.lat == 6.05
    village = Village.query.filter_by(municipality_id=velez.id).first()
    admin.post(f"/admin/veredas/{village.id}/ubicacion", data={"lat": "6.04", "lng": "-73.69"})
    db.session.refresh(village)
    assert (village.lat, village.lng) == (6.04, -73.69)
    admin.post(f"/admin/veredas/{village.id}/ubicacion", data={"lat": "", "lng": ""})
    db.session.refresh(village)
    assert village.lat is None
    assert "Centro aproximado" in admin.get(f"/admin/municipios/{velez.id}").get_data(as_text=True)

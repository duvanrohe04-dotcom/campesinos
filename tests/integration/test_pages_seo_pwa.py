from app.models import Listing, User

from ..conftest import url_of


def test_institutional_pages_render(client):
    for path, text in (("/quienes-somos", "Quiénes somos"), ("/como-funciona", "Si quieres vender"),
                       ("/preguntas-frecuentes", "Preguntas frecuentes"), ("/contacto", "Contacto y ayuda"),
                       ("/terminos", "BORRADOR"), ("/privacidad", "Ley 1581 de 2012")):  # fmt: skip
        response = client.get(path)
        assert response.status_code == 200 and text in response.get_data(as_text=True), path


def test_footer_links_on_every_page(client):
    html = client.get("/").get_data(as_text=True)
    for href in ("/como-funciona", "/preguntas-frecuentes", "/quienes-somos", "/contacto", "/terminos", "/privacidad"):
        assert f'href="{href}"' in html


def test_faq_has_structured_data(client):
    assert '"FAQPage"' in client.get("/preguntas-frecuentes").get_data(as_text=True)


def test_seo_and_pwa_endpoints(client):
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "Sitemap:" in robots and "Disallow: /admin/" in robots
    sitemap = client.get("/sitemap.xml")
    assert sitemap.mimetype == "application/xml" and "/bovinos/" in sitemap.get_data(as_text=True)
    service_worker = client.get("/sw.js")
    assert service_worker.status_code == 200 and service_worker.headers["Service-Worker-Allowed"] == "/"
    assert client.get("/static/manifest.webmanifest").status_code == 200
    assert client.get("/offline").status_code == 200


def test_structured_data_and_open_graph(client):
    listing = Listing.query.filter(Listing.title.contains("Novillo cebú")).first()
    html = client.get(url_of(listing)).get_data(as_text=True)
    assert 'property="og:title"' in html and '"@type": "Product"' in html and '"priceCurrency": "COP"' in html
    user = User.by_phone("3101112233")
    assert '"LocalBusiness"' in client.get(f"/vendedor/{user.id}").get_data(as_text=True)

"""Páginas de error amigables, alias de URL y cookies propias de la app."""


def test_cookie_names_are_app_specific(app):
    assert app.config["SESSION_COOKIE_NAME"] == "campo_directo_session"
    assert app.config["REMEMBER_COOKIE_NAME"] == "campo_directo_remember"


def test_method_not_allowed_shows_friendly_page(client):
    response = client.get("/salir")
    assert response.status_code == 405
    assert "Esa página no se abre así" in response.get_data(as_text=True)


def test_payload_too_large_shows_friendly_page(app, seller):
    app.config["MAX_CONTENT_LENGTH"] = 100
    response = seller.post("/publicar", data={"title": "x" * 500})
    assert response.status_code == 413
    assert "Las fotos pesan demasiado" in response.get_data(as_text=True)


def test_home_category_tiles_use_photos(client):
    html = client.get("/").get_data(as_text=True)
    assert "img/categorias/bovinos.webp" in html and "img/categorias/agricolas.webp" in html


def test_favicon_redirects_to_icon(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 301 and "icon-192.png" in response.headers["Location"]


def test_login_and_register_aliases(client):
    assert client.get("/login").headers["Location"].endswith("/ingresar")
    assert client.get("/register").headers["Location"].endswith("/registro")

import io

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Listing, User

from ..conftest import login, png_bytes, url_of

XSS = "<script>alert(1)</script>"


def test_user_content_is_escaped_in_pages(seller):
    listing = Listing.query.filter(Listing.user.has(User.phone == "3101112233")).first()
    listing.title, listing.description = f"Vendo {XSS}", f"Detalle {XSS}"
    user = User.by_phone("3101112233")
    user.farm_name, user.bio = f"Finca {XSS}", f"Bio {XSS}"
    db.session.commit()
    for path in (url_of(listing), "/anuncios", "/", f"/vendedor/{user.id}", "/panel"):
        assert XSS not in seller.get(path).get_data(as_text=True), path
    assert "&lt;script&gt;" in seller.get(url_of(listing)).get_data(as_text=True)


def test_search_is_safe_against_sql_injection_and_wildcards(client):
    for payload in ("' OR 1=1 --", "%", "_", "'; DROP TABLE listings; --", "\\"):
        assert client.get("/anuncios", query_string={"q": payload}).status_code == 200
    assert Listing.query.count() > 0
    assert client.get("/anuncios", query_string={"cat": "bovinos", "a_sexo": "' OR '1'='1"}).status_code == 200
    assert client.get("/anuncios", query_string={"mun": "1;DROP", "pmin": "abc", "page": "-5"}).status_code == 200


def test_csrf_is_enforced_when_enabled(tmp_path):
    class Config(TestingConfig):
        WTF_CSRF_ENABLED = True
        UPLOAD_FOLDER = str(tmp_path)

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        client = app.test_client()
        assert client.post("/salir").status_code in (302, 400)
        response = client.post("/registro", data={"name": "x"})  # sin token: se rechaza con página amable
        assert response.status_code == 400 and "ya venció" in response.get_data(as_text=True)
        assert User.query.count() == 0
        db.drop_all()


def test_inactive_user_loses_access(client):
    login(client, "3112223344")
    assert client.get("/panel").status_code == 200
    user = User.by_phone("3112223344")
    user.is_enabled = False
    db.session.commit()
    assert client.get("/panel").status_code == 302  # de vuelta al login
    assert login(client, "3112223344").status_code == 200  # no puede volver a entrar


def test_uploads_reject_scripts_disguised_as_images(seller):
    cases = [("shell.php", b"<?php echo 1; ?>"), ("x.svg", b"<svg onload=alert(1)>"), ("x.png", b"<script>1</script>")]
    for name, content in cases:
        data = {"ad_type": "vendo", "photos": (io.BytesIO(content), name)}
        assert seller.post("/publicar", data=data, content_type="multipart/form-data").status_code == 200
    assert png_bytes()

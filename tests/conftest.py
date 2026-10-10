import io

import pytest
from flask import current_app
from PIL import Image

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.services.seeding import seed_all
from app.templating import listing_url as _listing_url


@pytest.fixture()
def app(tmp_path):
    class Config(TestingConfig):
        UPLOAD_FOLDER = str(tmp_path)
        ADMIN_PHONE = "3000000000"
        ADMIN_PASSWORD = "admin12345"

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        seed_all(samples=True)
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, phone, password="campo123"):
    return client.post("/ingresar", data={"phone": phone, "password": password}, follow_redirects=False)


@pytest.fixture()
def seller(client):
    login(client, "3101112233")
    return client


@pytest.fixture()
def admin(client):
    login(client, "3000000000", "admin12345")
    return client


def png_bytes(size=(1600, 1200), color=(30, 120, 40)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    buf.seek(0)
    return buf


def url_of(listing):
    """URL canónica de un anuncio (fuera de una petición)."""
    with current_app.test_request_context():
        return _listing_url(listing)

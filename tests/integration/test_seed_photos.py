import json
import os

from app.extensions import db
from app.models import Listing, ListingImage
from app.services import seed_photos

from ..conftest import url_of


def test_every_photo_listed_in_credits_exists_with_license():
    credits = json.loads((seed_photos.PHOTOS_DIR / "credits.json").read_text(encoding="utf-8"))
    assert len(credits) >= 45
    for name, info in credits.items():
        assert (seed_photos.PHOTOS_DIR / f"{name}.jpg").exists(), name
        assert info["author"] and info["license"] and info["source"].startswith("https://commons.wikimedia.org/")
        assert "NC" not in info["license"] and "ND" not in info["license"]  # solo licencias que permiten reutilizar
    assert (seed_photos.PHOTOS_DIR / "CREDITOS.md").exists()


def test_every_photo_name_used_by_seed_exists():
    names = {n for options in seed_photos.PHOTOS_BY_SUBCATEGORY.values() for n in options}
    missing = [n for n in names if not (seed_photos.PHOTOS_DIR / f"{n}.jpg").exists()]
    assert not missing


def test_seed_photos_gives_each_listing_its_own_copy_and_skips_wanted_ads(app):
    assert ListingImage.query.count() == 0  # el seed de pruebas no carga fotos
    given = seed_photos.seed_photos()
    expected = [
        l for l in Listing.query.filter(Listing.ad_type != "compro")  # noqa: E741
        if l.category.slug in seed_photos.PHOTOS_BY_SUBCATEGORY
    ]  # fmt: skip
    assert given == len(expected) and given >= 10  # los de «Compro/Busco» y las categorías sin foto quedan sin foto
    files = [i.filename for i in ListingImage.query.all()]
    assert len(files) == len(set(files))  # sin archivos compartidos: borrar un anuncio no daña a otro
    folder = app.config["UPLOAD_FOLDER"]
    assert all(f in os.listdir(folder) and f.replace(".webp", "_t.webp") in os.listdir(folder) for f in files)
    assert all(not l.images for l in Listing.query.filter_by(ad_type="compro"))  # noqa: E741
    assert seed_photos.seed_photos() == 0  # idempotente


def test_detail_shows_photo_credit_and_deleting_one_listing_keeps_others(client, app):
    seed_photos.seed_photos()
    listing = Listing.query.filter(Listing.title.contains("Novillo cebú")).first()
    html = client.get(url_of(listing)).get_data(as_text=True)
    assert "Wikimedia Commons" in html and "Foto:" in html and "commons.wikimedia.org" in html
    other = Listing.query.filter(Listing.id != listing.id, Listing.images.any()).first()
    other_file = other.images[0].filename
    from app.services import images

    for image in listing.images:
        images.delete_files(image.filename)
    db.session.delete(listing)
    db.session.commit()
    assert other_file in os.listdir(app.config["UPLOAD_FOLDER"])

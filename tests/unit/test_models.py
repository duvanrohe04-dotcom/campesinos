from datetime import timedelta

from app.extensions import db
from app.models import Category, Listing, User
from app.services.expiry import expire_listings, renew
from app.utils import utcnow


def test_password_is_hashed(app):
    user = User.by_phone("3101112233")
    assert user.password_hash != "campo123" and user.check_password("campo123")


def test_lockout_after_failed_attempts_and_expiry(app):
    user = User.by_phone("3101112233")
    for _ in range(app.config["MAX_LOGIN_ATTEMPTS"]):
        user.register_failure()
    assert user.is_locked()
    user.locked_until = utcnow() - timedelta(minutes=1)
    assert not user.is_locked()
    user.register_success()
    assert user.failed_logins == 0


def test_category_tree_units_and_ica(app):
    bovinos = Category.root_by_slug("bovinos")
    assert bovinos.requires_ica and len(bovinos.children) == 5
    novillos = Category.sub_by_slug("novillos")
    assert novillos.root.id == bovinos.id and "kilo en pie" in novillos.units and novillos.needs_ica
    assert Category.root_by_slug("novillos") is None


def test_listing_query_helpers_and_properties(app):
    listing = Listing.public_query().first()
    assert listing.status == "active" and listing.slug and listing.location_text
    listing.expires_at = utcnow() + timedelta(days=2)
    assert listing.expiring_soon
    listing.expires_at = utcnow() + timedelta(days=20)
    assert not listing.expiring_soon


def test_expire_and_renew(app):
    listing = Listing.query.filter_by(status="active").first()
    listing.expires_at = utcnow() - timedelta(days=1)
    db.session.commit()
    assert expire_listings() == 1
    assert db.session.get(Listing, listing.id).status == "expired"
    renew(listing)
    assert listing.status == "active" and listing.expires_at > utcnow()

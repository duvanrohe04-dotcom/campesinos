"""Regresiones de la revisión de código: entradas raras y acciones que no deben saltarse reglas."""

import math
import re

import pytest

from app.constants import STATUS_ACTIVE, STATUS_PAUSED, STATUS_REMOVED
from app.extensions import db
from app.models import AttributeDef, Category, Listing, User, VerificationCode
from app.services import mailer, verification
from app.utils import utcnow

from ..conftest import login


def _own_listing(phone="3101112233") -> Listing:
    return Listing.query.filter(Listing.user.has(User.phone == phone)).first()


def test_search_ignores_non_finite_prices(client):
    for value in ("nan", "inf", "-inf", "1e999"):
        response = client.get("/anuncios", query_string={"pmin": value, "pmax": value})
        assert response.status_code == 200, value


def test_decimal_attribute_rejects_nan_and_infinity(app):
    from app.services.attributes import coerce

    definition = AttributeDef(key="peso", label="Peso", type="decimal")
    for raw in ("nan", "inf", "-inf", "1e999"):
        try:
            coerce(definition, raw, {})
        except ValueError:
            continue
        raise AssertionError(f"{raw} no debería aceptarse")
    assert math.isclose(coerce(definition, "12,5", {}), 12.5)


def test_admin_attribute_form_rejects_non_finite_limits(admin):
    category = Category.root_by_slug("bovinos")
    data = {"label": "Dato raro", "type": "int", "min_value": "nan", "max_value": ""}
    response = admin.post(f"/admin/categorias/{category.id}/atributos/nuevo", data=data)
    assert response.status_code == 200  # el formulario vuelve con el error
    assert "Escribe un número." in response.get_data(as_text=True)
    assert not AttributeDef.query.filter_by(category_id=category.id, label="Dato raro").count()


def test_login_next_with_backslash_does_not_leave_the_site(client):
    response = client.post(
        "/ingresar?next=/%5Cevil.com", data={"phone": "3101112233", "password": "campo123"}, follow_redirects=False
    )
    assert response.status_code == 302 and response.headers["Location"] == "/"


def test_owner_cannot_reactivate_a_listing_removed_by_admin(seller):
    listing = _own_listing()
    listing.status = STATUS_REMOVED
    db.session.commit()
    for action in ("activar", "renovar", "vendido", "pausar"):
        assert seller.post(f"/panel/anuncio/{listing.id}/{action}").status_code == 404, action
        assert db.session.get(Listing, listing.id).status == STATUS_REMOVED
    assert seller.post(f"/panel/anuncio/{listing.id}/eliminar").status_code == 302  # sí puede borrarlo
    assert db.session.get(Listing, listing.id) is None


def test_reactivating_respects_the_active_listing_cap(app, seller):
    app.config["MAX_ACTIVE_LISTINGS"] = 1
    user = User.by_phone("3101112233")
    active = Listing.query.filter_by(user_id=user.id, status=STATUS_ACTIVE).all()
    for extra in active[1:]:
        extra.status = STATUS_PAUSED
    paused = active[1]
    db.session.commit()
    assert Listing.query.filter_by(user_id=user.id, status=STATUS_ACTIVE).count() == 1
    response = seller.post(f"/panel/anuncio/{paused.id}/activar", follow_redirects=True)
    assert "máximo" in response.get_data(as_text=True)
    assert db.session.get(Listing, paused.id).status == STATUS_PAUSED


def test_admin_restore_gives_an_expired_listing_a_new_deadline(admin):
    listing = _own_listing()
    listing.status = STATUS_REMOVED
    listing.expires_at = utcnow().replace(year=2020)
    db.session.commit()
    admin.post(f"/admin/anuncios/{listing.id}/restaurar")
    restored = db.session.get(Listing, listing.id)
    assert restored.status == STATUS_ACTIVE and restored.expires_at > utcnow()


def test_admin_cannot_reactivate_a_deleted_account(app, client):
    user = User.by_phone("3112223344")
    user.is_enabled, user.deleted_at = False, utcnow()
    db.session.commit()
    login(client, "3000000000", "admin12345")
    client.post(f"/admin/usuarios/{user.id}/estado")
    assert db.session.get(User, user.id).is_enabled is False


def test_old_code_does_not_verify_a_new_email(seller):
    mailer.outbox.clear()
    user = User.by_phone("3101112233")
    user.email_verified_at = None
    db.session.commit()
    seller.post("/verificar-correo/enviar")
    old_code = re.search(r"\b(\d{6})\b", mailer.outbox[-1].body).group(1)
    data = {"name": user.name, "municipality_id": user.municipality_id, "email": "nuevo.correo@example.com"}
    seller.post("/panel/perfil", data=data)

    user = User.by_phone("3101112233")
    assert user.email == "nuevo.correo@example.com" and not user.email_verified
    # El código del correo anterior ya no sirve, aunque no hayan pasado los 60 s para pedir otro
    assert VerificationCode.query.filter_by(user_id=user.id, used_at=None).count() <= 1
    with pytest.raises(verification.VerificationError):
        verification.confirm_code(user, old_code)
    assert not User.by_phone("3101112233").email_verified

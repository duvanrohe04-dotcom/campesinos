import re

from app.extensions import db
from app.models import Rating, User
from app.services import mailer

from ..conftest import login, url_of


def last_code():
    """Código de 6 números del último correo enviado."""
    return re.search(r"\b(\d{6})\b", mailer.outbox[-1].body).group(1)


def give_email(phone, email):
    user = User.by_phone(phone)
    user.email = email
    db.session.commit()
    return user


def test_email_verification_flow(seller):
    mailer.outbox.clear()
    user = give_email("3112223344", "marta@example.com")
    seller.post("/salir")
    login(seller, user.phone)
    assert "Verifica tu correo" in seller.get("/panel").get_data(as_text=True)

    assert seller.post("/verificar-correo/enviar").status_code == 302
    assert mailer.outbox and mailer.outbox[-1].to == "marta@example.com"
    wrong = seller.post("/verificar-correo", data={"code": "000000" if last_code() != "000000" else "111111"})
    assert "no es correcto" in wrong.get_data(as_text=True)
    assert not db.session.get(User, user.id).email_verified

    ok = seller.post("/verificar-correo", data={"code": last_code()})
    assert ok.status_code == 302
    assert db.session.get(User, user.id).email_verified
    assert "Verifica tu correo" not in seller.get("/panel").get_data(as_text=True)


def test_verifying_without_email_sends_to_profile(client):
    login(client, "3123334455")
    response = client.get("/verificar-correo")
    assert response.status_code == 302 and response.headers["Location"].endswith("/panel/perfil")
    assert "Agrega tu correo" in client.get("/panel").get_data(as_text=True)


def test_code_resend_cooldown_and_attempt_limit(client):
    mailer.outbox.clear()
    give_email("3123334455", "luis@example.com")
    login(client, "3123334455")
    client.post("/verificar-correo/enviar")
    again = client.post("/verificar-correo/enviar", follow_redirects=True)
    assert "Espera" in again.get_data(as_text=True) and len(mailer.outbox) == 1
    real = last_code()
    bad = "999999" if real != "999999" else "888888"
    for _ in range(5):
        client.post("/verificar-correo", data={"code": bad})
    blocked = client.post("/verificar-correo", data={"code": real})
    assert "Demasiados intentos" in blocked.get_data(as_text=True)


def test_expired_code_is_rejected(client):
    from datetime import timedelta

    from app.models import VerificationCode
    from app.utils import utcnow

    mailer.outbox.clear()
    give_email("3123334455", "luis@example.com")
    login(client, "3123334455")
    client.post("/verificar-correo/enviar")
    VerificationCode.query.update({"expires_at": utcnow() - timedelta(minutes=1)})
    db.session.commit()
    assert "venció" in client.post("/verificar-correo", data={"code": last_code()}).get_data(as_text=True)


def test_mail_failure_does_not_burn_the_cooldown(client, monkeypatch):
    def boom(*_args, **_kwargs):
        raise mailer.MailError("sin conexión")

    give_email("3123334455", "luis@example.com")
    login(client, "3123334455")
    monkeypatch.setattr(mailer, "send_email", boom)
    html = client.post("/verificar-correo/enviar", follow_redirects=True).get_data(as_text=True)
    assert "No pudimos enviar el correo" in html and "Traceback" not in html
    monkeypatch.undo()
    mailer.outbox.clear()
    assert "Espera" not in client.post("/verificar-correo/enviar", follow_redirects=True).get_data(as_text=True)
    assert len(mailer.outbox) == 1


def test_verified_badge_given_by_admin(admin):
    seller = User.by_phone("3123334455")
    admin.post(f"/admin/usuarios/{seller.id}/verificado")
    db.session.refresh(seller)
    assert seller.is_verified_seller
    assert "Vendedor verificado" in admin.get(f"/vendedor/{seller.id}").get_data(as_text=True)
    admin.post(f"/admin/usuarios/{seller.id}/verificado")
    db.session.refresh(seller)
    assert not seller.is_verified_seller


def test_rating_requires_login_and_blocks_self_rating(client):
    seller = User.by_phone("3123334455")
    assert client.post(f"/vendedor/{seller.id}/calificar", data={"stars": "5"}).status_code == 302
    assert Rating.query.filter_by(seller_id=seller.id).count() == 0
    login(client, seller.phone)
    html = client.post(f"/vendedor/{seller.id}/calificar", data={"stars": "5"}, follow_redirects=True).get_data(
        as_text=True
    )
    assert "No puedes calificarte" in html


def test_one_rating_per_user_and_update(client):
    seller = User.by_phone("3123334455")
    login(client, "3134445566")
    client.post(f"/vendedor/{seller.id}/calificar", data={"stars": "5", "comment": "Excelente"})
    client.post(f"/vendedor/{seller.id}/calificar", data={"stars": "3", "comment": "Cambié de opinión"})
    ratings = Rating.query.filter_by(seller_id=seller.id).all()
    assert len(ratings) == 1 and ratings[0].stars == 3
    html = client.get(f"/vendedor/{seller.id}").get_data(as_text=True)
    assert "Cambié de opinión" in html and "Cambiar mi calificación" in html
    invalid = client.post(f"/vendedor/{seller.id}/calificar", data={"stars": "9"}, follow_redirects=True)
    assert Rating.query.filter_by(seller_id=seller.id).one().stars == 3 and invalid.status_code == 200


def test_reputation_on_profile_and_detail(client):
    jorge = User.by_phone("3101112233")  # sembrado con insignia, 2 calificaciones (5 y 4)
    html = client.get(f"/vendedor/{jorge.id}").get_data(as_text=True)
    assert "4.5" in html and "Vendedor verificado" in html and "Correo verificado" in html
    assert "aggregateRating" in html
    listing = jorge.listings.first()
    assert "Vendedor verificado" in client.get(url_of(listing)).get_data(as_text=True)


def test_admin_hides_rating(admin):
    rating = Rating.query.first()
    seller_id = rating.seller_id
    admin.post(f"/admin/calificaciones/{rating.id}/ocultar")
    db.session.refresh(rating)
    assert rating.status == "hidden"
    assert rating.comment not in admin.get(f"/vendedor/{seller_id}").get_data(as_text=True)
    assert admin.get("/admin/calificaciones?estado=hidden").status_code == 200


def test_safety_tips_page_and_links(client):
    html = client.get("/consejos-compra-segura").get_data(as_text=True)
    assert "No pagues por adelantado" in html and "guía sanitaria" in html
    assert "/consejos-compra-segura" in client.get("/").get_data(as_text=True)

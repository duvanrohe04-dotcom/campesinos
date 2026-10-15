"""Carga de datos iniciales (idempotente). Los datos están en seed_data.py."""

from datetime import timedelta

from flask import current_app

from ..constants import PHONE_MAX
from ..extensions import db
from ..models import Article, AttributeDef, Category, Event, Listing, Municipality, Rating, User, Village
from ..utils import slugify, utcnow
from .articles import save_article
from .prices import backfill_snapshots
from .seed_articles import ARTICLES
from .seed_data import CATEGORIES, MUNICIPALITIES, SAMPLE_VILLAGES, SAMPLES
from .seed_extra import EXTRA_PEOPLE, EXTRA_SAMPLES, PRICE_CLUSTERS, PRICE_FACTORS
from .seed_photos import seed_photos


def seed_categories():
    for pos, c in enumerate(CATEGORIES):
        root = Category.query.filter_by(slug=c["slug"]).first()
        if not root:
            root = Category(slug=c["slug"])
            db.session.add(root)
        root.name, root.icon, root.position = c["name"], c["icon"], pos
        root.home_section, root.requires_ica = c.get("home_section"), c.get("requires_ica", False)
        root.price_units = c["units"]
        db.session.flush()
        for i, name in enumerate(c["subs"]):
            slug = slugify(name)
            sub = Category.query.filter_by(slug=slug).first()
            if not sub:
                sub = Category(slug=slug)
                db.session.add(sub)
            sub.name, sub.parent_id, sub.position, sub.icon = name, root.id, i, c["icon"]
        for i, a in enumerate(c["attrs"]):
            d = AttributeDef.query.filter_by(category_id=root.id, key=a["key"]).first() or AttributeDef(
                category_id=root.id, key=a["key"]
            )
            d.label, d.type, d.position = a["label"], a["type"], i
            d.required, d.choices = a.get("required", False), a.get("choices")
            d.min_value, d.max_value, d.unit = a.get("min_value"), a.get("max_value"), a.get("unit")
            d.help_text, d.is_filterable = a.get("help_text"), a.get("is_filterable", False)
            db.session.add(d)
    db.session.commit()


def seed_geo():
    for name, (lat, lng) in MUNICIPALITIES.items():
        m = Municipality.query.filter_by(slug=slugify(name)).first()
        if not m:
            m = Municipality(name=name, slug=slugify(name))
            db.session.add(m)
            db.session.flush()
            for v in SAMPLE_VILLAGES:
                db.session.add(Village(municipality_id=m.id, name=v))
        if m.lat is None or m.lng is None:  # no pisa coordenadas corregidas por el admin
            m.lat, m.lng = lat, lng
    db.session.commit()


class SeedConfigError(RuntimeError):
    """Falta una variable de entorno necesaria para cargar los datos."""


def admin_login() -> str:
    """Usuario del administrador (ADMIN_PHONE): un celular o una palabra como «admin», siempre en minúsculas."""
    return (current_app.config.get("ADMIN_PHONE") or "").strip().lower()


def seed_admin() -> bool:
    """Crea el administrador con ADMIN_PHONE y ADMIN_PASSWORD del entorno. Si no están definidos, no hace nada.
    Devuelve si se creó."""
    cfg = current_app.config
    phone, password = admin_login(), cfg.get("ADMIN_PASSWORD")
    if not (phone and password):
        current_app.logger.warning("ADMIN_PHONE/ADMIN_PASSWORD no definidos: no se creó administrador.")
        return False
    if len(phone) > PHONE_MAX:
        current_app.logger.error("ADMIN_PHONE debe tener máximo %s caracteres: no se creó administrador.", PHONE_MAX)
        return False
    if User.query.filter_by(phone=phone).first():
        return False
    admin = User(
        name="Administrador",
        phone=phone,
        role="admin",
        municipality=Municipality.query.filter_by(slug="velez").first(),
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return True


def seed_demo_users() -> None:
    """Usuarios de DEMOSTRACIÓN con la clave DEMO_PASSWORD. Nunca para producción."""
    password = current_app.config.get("DEMO_PASSWORD")
    if not password:
        raise SeedConfigError("Define DEMO_PASSWORD en el entorno para crear los usuarios de ejemplo.")
    people = [
        ("Don Jorge Rojas", "3101112233", "seller", "velez", "Finca La Esperanza"),
        ("Marta Cárdenas", "3112223344", "seller", "barbosa", "Finca El Mirador"),
        ("Luis Pinzón", "3123334455", "seller", "puente-nacional", None),
        ("Carlos Gómez", "3134445566", "buyer", "velez", None),
    ]
    for name, phone, role, mun, farm in people:
        if not User.query.filter_by(phone=phone).first():
            u = User(
                name=name,
                phone=phone,
                role=role,
                farm_name=farm,
                municipality=Municipality.query.filter_by(slug=mun).first(),
            )
            u.set_password(password)
            db.session.add(u)
    db.session.commit()
    _seed_reputation()


def _seed_reputation() -> None:
    """Insignia, correo verificado y un par de calificaciones de ejemplo (idempotente)."""
    jorge, marta = User.by_phone("3101112233"), User.by_phone("3112223344")
    buyer = User.by_phone("3134445566")
    if not (jorge and marta and buyer):
        return
    jorge.is_verified_seller = True
    jorge.email = jorge.email or "jorge.rojas@example.com"
    jorge.email_verified_at = jorge.email_verified_at or utcnow()
    if not Rating.query.filter_by(seller_id=jorge.id, rater_id=buyer.id).first():
        db.session.add(
            Rating(seller_id=jorge.id, rater_id=buyer.id, stars=5, comment="Todo como en las fotos, muy cumplido.")
        )
    if not Rating.query.filter_by(seller_id=jorge.id, rater_id=marta.id).first():
        db.session.add(Rating(seller_id=jorge.id, rater_id=marta.id, stars=4, comment="Buen trato y buen precio."))
    db.session.commit()


def seed_samples():
    if Listing.query.count():
        return 0
    sellers = User.query.filter_by(role="seller").order_by(User.id).all()
    buyer = User.query.filter_by(role="buyer").first()
    n = 0
    for i, (_root_slug, sub_name, ad, title, desc, price, unit, qty, attrs, mun_name) in enumerate(SAMPLES):
        sub = Category.query.filter_by(slug=slugify(sub_name)).first()
        mun = Municipality.query.filter_by(slug=slugify(mun_name)).first()
        owner = buyer if ad == "compro" else sellers[i % len(sellers)]
        village = Village.query.filter_by(municipality_id=mun.id, name="Centro").first()
        listing = Listing(
            user=owner,
            category=sub,
            ad_type=ad,
            title=title,
            description=desc,
            price=price,
            price_unit=unit,
            quantity=qty,
            attrs=attrs,
            municipality=mun,
            village=village,
            negotiable=i % 2 == 0,
            created_at=utcnow() - timedelta(hours=3 + i * 7),
        )
        listing.set_expiry()
        db.session.add(listing)
        n += 1
    db.session.commit()
    return n


def seed_articles() -> int:
    """Consejos iniciales (idempotente, por título). Autor: el administrador."""
    admin = User.query.filter_by(phone=admin_login()).first() if admin_login() else None
    created = 0
    for item in ARTICLES:
        if Article.query.filter_by(title=item["title"]).first():
            continue
        save_article(
            None, title=item["title"], summary=item["summary"], body=item["body"], category=item["category"],
            is_published=True, author_id=admin.id if admin else None,
        )  # fmt: skip
        created += 1
    return created


def seed_events() -> int:
    """Eventos de EJEMPLO (fechas relativas a hoy). Solo para desarrollo: no se cargan en producción."""
    if Event.query.count():
        return 0
    velez = Municipality.query.filter_by(slug="velez").first()
    today = utcnow().replace(hour=8, minute=0, second=0, microsecond=0)
    samples = [
        ("Feria ganadera de ejemplo", "feria", 9, "Recinto ferial", "Alcaldía (ejemplo)"),
        ("Jornada de vacunación de ejemplo", "vacunacion", 16, "Casa campesina", "ICA (ejemplo)"),
        ("Mercado campesino de ejemplo", "mercado", 5, "Plaza principal", "Asociación de productores (ejemplo)"),
    ]
    for title, kind, days, place, organizer in samples:
        db.session.add(
            Event(title=title, kind=kind, starts_at=today + timedelta(days=days), place=place, organizer=organizer,
                  municipality=velez, description="Evento de demostración: reemplázalo desde Admin → Agenda.")
        )  # fmt: skip
    db.session.commit()
    return len(samples)


def seed_extra() -> int:
    """Más usuarios y anuncios de DEMOSTRACIÓN (todas las categorías, varios municipios). Solo desarrollo."""
    password = current_app.config.get("DEMO_PASSWORD")
    if not password:
        raise SeedConfigError("Define DEMO_PASSWORD en el entorno para crear los usuarios de ejemplo.")
    for name, phone, role, mun_slug, farm, bio in EXTRA_PEOPLE:
        if not User.query.filter_by(phone=phone).first():
            user = User(name=name, phone=phone, role=role, farm_name=farm, bio=bio,
                        municipality=Municipality.query.filter_by(slug=mun_slug).first())  # fmt: skip
            user.set_password(password)
            db.session.add(user)
    db.session.commit()
    if Listing.query.filter_by(title=EXTRA_SAMPLES[0][3]).first():
        return 0

    sellers = User.query.filter_by(role="seller").order_by(User.id).all()
    buyers = User.query.filter_by(role="buyer").order_by(User.id).all()
    created = 0
    for i, (_root, sub_name, ad, title, desc, price, unit, qty, attrs, mun_name) in enumerate(EXTRA_SAMPLES):
        category = Category.query.filter_by(slug=slugify(sub_name)).first()
        municipality = Municipality.query.filter_by(slug=slugify(mun_name)).first()
        if not (category and municipality):
            continue
        owner = buyers[i % len(buyers)] if ad == "compro" else sellers[i % len(sellers)]
        village = Village.query.filter_by(
            municipality_id=municipality.id, name=SAMPLE_VILLAGES[i % len(SAMPLE_VILLAGES)]
        ).first()
        listing = Listing(
            user=owner, category=category, ad_type=ad, title=title, description=desc, price=price, price_unit=unit,
            quantity=qty, attrs=attrs, municipality=municipality, village=village, negotiable=i % 3 != 0,
            created_at=utcnow() - timedelta(hours=2 + i * 13),
        )  # fmt: skip
        listing.set_expiry()
        db.session.add(listing)
        created += 1
    db.session.commit()
    return created


def seed_price_clusters() -> int:
    """Anuncios parecidos con precios algo distintos y fechas repartidas en ~4 semanas (demostración)."""
    if Listing.query.filter_by(title=PRICE_CLUSTERS[0][3][0] + " ·1").first():
        return 0
    sellers = User.query.filter_by(role="seller").order_by(User.id).all()
    municipalities = Municipality.query.filter(
        Municipality.slug.in_(["velez", "barbosa", "puente-nacional", "guavata", "chipata"])
    ).all()
    created = 0
    for c, (sub_name, unit, base, titles, attrs) in enumerate(PRICE_CLUSTERS):
        category = Category.query.filter_by(slug=slugify(sub_name)).first()
        if not category:
            continue
        for i, title in enumerate(titles):
            municipality = municipalities[(c + i) % len(municipalities)]
            listing = Listing(
                user=sellers[(c + i) % len(sellers)], category=category, ad_type="vendo", title=f"{title} ·{i + 1}",
                description="Anuncio de demostración para calcular precios de referencia.",
                price=round(base * PRICE_FACTORS[i], -2 if base < 100000 else -3), price_unit=unit,
                quantity=10 + i * 5, attrs=attrs, municipality=municipality, negotiable=i % 2 == 0,
                created_at=utcnow() - timedelta(days=2 + i * 6 + c % 3, hours=c * 2),
            )  # fmt: skip
            listing.set_expiry()
            db.session.add(listing)
            created += 1
    db.session.commit()
    return created


def seed_all(samples: bool = True, extra: bool = False) -> int:
    """Datos base (siempre) y, con `samples`, usuarios, eventos y anuncios de demostración (solo desarrollo)."""
    seed_categories()
    seed_geo()
    seed_admin()
    seed_articles()
    if not samples:
        return 0
    seed_demo_users()
    seed_events()
    created = seed_samples()
    if not extra:
        return created
    created += seed_extra()
    created += seed_price_clusters()
    seed_photos()  # fotos reales (libres) para los anuncios de demostración
    backfill_snapshots()  # precios de referencia e histórico con los anuncios de ejemplo
    return created

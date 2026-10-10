"""Lógica de las páginas generales: secciones del inicio, contacto y sitemap."""

from xml.sax.saxutils import escape

from flask import url_for
from flask_login import current_user

from ...constants import SITEMAP_MAX_LISTINGS, STATUS_ACTIVE
from ...extensions import db
from ...models import Category, ContactMessage, Listing
from ...services import articles as article_service
from ...templating import listing_url


def section_listings(section: str, limit: int = 4) -> list[Listing]:
    """Últimos anuncios de las categorías que el admin asignó a una sección del inicio."""
    ids = [
        cid
        for root in Category.query.filter_by(parent_id=None, home_section=section, is_active=True)
        for cid in root.family_ids
    ]
    if not ids:
        return []
    return (
        Listing.public_query()
        .filter(Listing.category_id.in_(ids))
        .order_by(Listing.created_at.desc())
        .limit(limit)
        .all()
    )


def recent_listings(limit: int = 8) -> list[Listing]:
    return Listing.public_query().order_by(Listing.created_at.desc()).limit(limit).all()


def save_contact_message(form) -> ContactMessage:
    message = ContactMessage(
        name=form.name.data.strip(),
        contact=form.contact.data.strip(),
        subject=form.subject.data,
        message=form.message.data.strip(),
        user_id=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(message)
    db.session.commit()
    return message


def robots_txt() -> str:
    return (
        "User-agent: *\nDisallow: /admin/\nDisallow: /panel/\nDisallow: /publicar\n"
        "Disallow: /anuncio/*/contacto\nDisallow: /anuncio/*/whatsapp\nDisallow: /vendedor/*/contacto\n"
        f"Sitemap: {url_for('main.sitemap', _external=True)}\n"
    )


def sitemap_xml() -> str:
    urls = [url_for("main.home", _external=True), url_for("listings.index", _external=True)]
    urls += [url_for("listings.index", cat=c.slug, _external=True) for c in Category.active_roots()]
    urls += [
        listing_url(listing, external=True)
        for listing in Listing.public_query()
        .filter(Listing.status == STATUS_ACTIVE)
        .order_by(Listing.created_at.desc())
        .limit(SITEMAP_MAX_LISTINGS)
    ]
    urls += [
        url_for("agenda.index", _external=True),
        url_for("tips.index", _external=True),
        url_for("prices.index", _external=True),
    ]
    urls += [url_for("tips.detail", slug=a.slug, _external=True) for a in article_service.published_query().limit(500)]
    body = "".join(f"<url><loc>{escape(u)}</loc></url>\n" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>'
    )

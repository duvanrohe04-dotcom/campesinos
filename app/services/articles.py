"""Consejos del campo: sanitización del HTML, tiempo de lectura, slugs y artículos relacionados."""

import re

import nh3
from sqlalchemy.orm import joinedload

from ..constants import (
    ARTICLE_ALLOWED_TAGS,
    ARTICLE_CATEGORIES,
    ARTICLE_LISTING_CATEGORY,
    READING_WORDS_PER_MINUTE,
)
from ..extensions import db
from ..models import Article, Category
from ..utils import slugify


def sanitize_html(html: str) -> str:
    """Deja solo etiquetas seguras (sin scripts, estilos ni eventos). Los enlaces llevan rel seguro."""
    # El editor usa h1 para títulos; dentro de la página el h1 es el del artículo: se baja a h2 antes de limpiar
    html = re.sub(r"<(/?)h1\b", r"<\1h2", html or "")
    return nh3.clean(
        html,
        tags=ARTICLE_ALLOWED_TAGS,
        attributes={"a": {"href"}},
        url_schemes={"http", "https", "mailto", "tel"},
        link_rel="noopener noreferrer nofollow",
    )


def plain_text(html: str) -> str:
    return re.sub(r"\s+", " ", nh3.clean(html or "", tags=set())).strip()


def reading_minutes(html: str) -> int:
    words = len(plain_text(html).split())
    return max(1, round(words / READING_WORDS_PER_MINUTE))


def unique_slug(title: str, exclude_id: int | None = None) -> str:
    base = slugify(title, 100)
    slug, n = base, 2
    while True:
        clash = Article.query.filter_by(slug=slug).first()
        if not clash or clash.id == exclude_id:
            return slug
        slug, n = f"{base}-{n}", n + 1


def published_query(category: str | None = None):
    query = Article.query.options(joinedload(Article.author)).filter(Article.is_published.is_(True))
    if category in ARTICLE_CATEGORIES:
        query = query.filter(Article.category == category)
    return query.order_by(Article.published_at.desc())


def related(article: Article, limit: int = 3) -> list[Article]:
    """Misma categoría primero; si faltan, completa con los más recientes."""
    same = published_query(article.category).filter(Article.id != article.id).limit(limit).all()
    if len(same) >= limit:
        return same
    ids = [a.id for a in same] + [article.id]
    rest = published_query().filter(Article.id.notin_(ids)).limit(limit - len(same)).all()
    return same + rest


def listing_category_for(article: Article) -> Category | None:
    """Categoría del marketplace relacionada con el tema del artículo (para enlazar a anuncios)."""
    slug = ARTICLE_LISTING_CATEGORY.get(article.category)
    return Category.root_by_slug(slug) if slug else None


def save_article(article: Article | None, *, title: str, summary: str, body: str, category: str,
                 is_published: bool, author_id: int | None = None, cover: str | None = None) -> Article:  # fmt: skip
    """Crea o actualiza un artículo con el cuerpo sanitizado."""
    target = article or Article(author_id=author_id)
    target.title, target.summary, target.category = title.strip(), summary.strip(), category
    target.body_html = sanitize_html(body)
    target.reading_minutes = reading_minutes(target.body_html)
    target.is_published = is_published
    if cover:
        target.cover = cover
    if not article:  # la dirección (slug) no cambia al editar el título: los enlaces compartidos siguen funcionando
        target.slug = unique_slug(target.title)
    db.session.add(target)
    db.session.commit()
    return target

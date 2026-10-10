"""Armado de las pantallas de «Consejos del campo»."""

from dataclasses import dataclass

from ...constants import ARTICLE_CATEGORIES, ARTICLES_PER_PAGE
from ...models import Article, Category
from ...services import articles as article_service


@dataclass
class TipsIndex:
    pagination: object
    category: str


def tips_index(category: str | None, page: int) -> TipsIndex:
    category = category if category in ARTICLE_CATEGORIES else ""
    query = article_service.published_query(category or None)
    pagination = query.paginate(page=page, per_page=ARTICLES_PER_PAGE, error_out=False)
    return TipsIndex(pagination, category)


@dataclass
class TipDetail:
    article: Article
    related: list[Article]
    listing_category: Category | None


def tip_detail(slug: str) -> TipDetail | None:
    article = Article.query.filter_by(slug=slug, is_published=True).first()
    if not article:
        return None
    return TipDetail(article, article_service.related(article), article_service.listing_category_for(article))

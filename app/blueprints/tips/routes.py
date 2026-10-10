from flask import abort, render_template, request

from ...constants import ARTICLE_CATEGORIES
from . import bp, services


@bp.route("/consejos")
def index():
    data = services.tips_index(request.args.get("categoria"), request.args.get("page", 1, type=int))
    return render_template("tips/index.html", p=data.pagination, category=data.category, categories=ARTICLE_CATEGORIES)


@bp.route("/consejos/<slug>")
def detail(slug):
    data = services.tip_detail(slug)
    if not data:
        abort(404)
    return render_template(
        "tips/detail.html", a=data.article, related=data.related, listing_category=data.listing_category,
        categories=ARTICLE_CATEGORIES,
    )  # fmt: skip

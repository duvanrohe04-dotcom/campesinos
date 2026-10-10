from datetime import timedelta

from app.extensions import db
from app.models import Category, Listing, Municipality, PriceSnapshot, User
from app.services import prices
from app.utils import utcnow


def test_outliers_are_discarded_with_iqr_rule():
    data = [2400, 2500, 2500, 2600, 2700, 2500, 99000, 10]
    kept = prices.remove_outliers(data)
    assert 99000 not in kept and 10 not in kept and len(kept) == 6


def test_small_samples_keep_everything_and_need_minimum():
    assert prices.remove_outliers([1000, 90000, 1000]) == [1000, 90000, 1000]
    assert prices.summarize([1000, 2000]) is None  # menos de 3 datos: no se publica
    summary = prices.summarize([1000, 2000, 3000])
    assert (summary.average, summary.median, summary.minimum, summary.maximum) == (2000, 2000, 1000, 3000)


def test_summary_reports_discarded_values():
    summary = prices.summarize([2400, 2500, 2500, 2600, 2700, 2500, 99000])
    assert summary.discarded == 1 and summary.maximum == 2700 and summary.sample_size == 6


def add_prices(values, slug="lechones", unit="animal", municipality="velez", days_ago=1, ad_type="vendo"):
    category = Category.sub_by_slug(slug)
    owner = User.by_phone("3101112233")
    mun = Municipality.query.filter_by(slug=municipality).one()
    for value in values:
        listing = Listing(
            user=owner,
            category=category,
            ad_type=ad_type,
            title=f"Lechón {value}",
            price=value,
            price_unit=unit,
            attrs={},
            municipality=mun,
            created_at=utcnow() - timedelta(days=days_ago),
        )
        listing.set_expiry()
        db.session.add(listing)
    db.session.commit()


def test_live_reference_prefers_municipality_then_region(app):
    add_prices([700000, 720000, 740000], municipality="velez")
    add_prices([500000, 520000, 540000], municipality="barbosa")
    category = Category.sub_by_slug("lechones")
    velez = Municipality.query.filter_by(slug="velez").one()
    local, scope = prices.live_reference(category, "animal", velez.id)
    assert scope == "municipio" and local.average == 720000
    bolivar = Municipality.query.filter_by(slug="bolivar").one()
    region, scope = prices.live_reference(category, "animal", bolivar.id)
    assert scope == "region" and region.sample_size == 6
    assert prices.live_reference(category, "kilo en pie")[0] is None


def test_wanted_ads_old_listings_and_by_agreement_are_excluded(app):
    add_prices([100, 100, 100], ad_type="compro")
    add_prices([100, 100, 100], days_ago=45)
    add_prices([100, 100, 100], unit="a convenir")
    assert prices.live_reference(Category.sub_by_slug("lechones"), "animal")[0] is None


def test_update_snapshots_is_idempotent_and_builds_history(app):
    add_prices([700000, 720000, 740000, 760000])
    assert prices.update_snapshots() == 1
    assert prices.update_snapshots() == 1  # mismo día: actualiza, no duplica
    assert PriceSnapshot.query.count() == 1
    old = PriceSnapshot(
        category_id=Category.sub_by_slug("lechones").id, unit="animal",
        day=utcnow().date() - timedelta(days=28), average=600000, median=600000, minimum=550000, maximum=650000,
        sample_size=5,
    )  # fmt: skip
    db.session.add(old)
    db.session.commit()
    row = prices.latest_rows()[0]
    assert row.snapshot.average == 730000 and row.change_percent == round((730000 - 600000) / 600000 * 100, 1)
    trend = prices.trend(row.category, "animal")
    assert len(trend.labels) == 2 and trend.averages[-1] == 730000

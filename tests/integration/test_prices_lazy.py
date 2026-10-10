from datetime import timedelta

from app.models import Category, PriceSnapshot
from app.services import prices
from app.utils import utcnow

from ..unit.test_prices import add_prices


def test_prices_page_calculates_itself_without_the_cron(client):
    add_prices([700000, 720000, 740000, 760000])
    assert PriceSnapshot.query.count() == 0  # nadie ha corrido `flask update-prices`
    html = client.get("/precios").get_data(as_text=True)
    assert "Lechones" in html and "730.000" in html and "Aún no hay suficientes" not in html
    assert PriceSnapshot.query.count() == 1


def test_refresh_runs_once_per_day(app):
    add_prices([100000, 110000, 120000])
    assert prices.refresh_if_stale() is True
    assert prices.refresh_if_stale() is False


def test_detail_page_also_refreshes(client):
    add_prices([100000, 110000, 120000])
    assert "$ 110.000" in client.get("/precios/lechones").get_data(as_text=True)


def test_backfill_builds_weekly_history_from_existing_listings(app):
    add_prices([100000, 110000, 120000], days_ago=20)  # anuncios de hace 20 días
    saved = prices.backfill_snapshots(weeks=4)
    category = Category.sub_by_slug("lechones")
    days = sorted(s.day for s in PriceSnapshot.query.filter_by(category_id=category.id))
    assert saved >= 2 and len(days) >= 2
    today = utcnow().date()
    assert days[-1] == today and days[0] <= today - timedelta(days=14)
    assert len(prices.trend(category, "animal").labels) >= 2


def test_snapshot_for_past_day_ignores_newer_listings(app):
    add_prices([100000, 110000, 120000], days_ago=2)
    past = utcnow().date() - timedelta(days=5)
    assert prices.update_snapshots(past) == 0  # esos anuncios aún no existían ese día
    assert prices.update_snapshots() == 1

import pytest

from app.models import Listing, Municipality, Village
from app.services import geo


def test_points_are_rounded_to_about_one_kilometre():
    assert geo.round_point(6.013912, -73.673651) == (6.01, -73.67)
    assert geo.parse_point("6,0139", "-73.6736") == (6.01, -73.67)
    assert geo.parse_point("", "") is None


@pytest.mark.parametrize(
    ("lat", "lng"), [("abc", "1"), ("6.0", ""), ("", "-73.6"), ("40.4", "-3.7"), ("nan", "-73"), ("91", "-73")]
)
def test_invalid_points_are_rejected(lat, lng):
    with pytest.raises(ValueError, match="punto"):
        geo.parse_point(lat, lng)


def test_haversine_and_bounding_box():
    velez, barbosa = (6.0139, -73.6736), (5.9331, -73.6169)
    assert 8 < geo.haversine_km(velez, barbosa) < 13
    assert geo.haversine_km(velez, velez) == 0
    lat_min, lat_max, lng_min, lng_max = geo.bounding_box(velez, 10)
    assert lat_min < velez[0] < lat_max and lng_min < velez[1] < lng_max
    assert 0.085 < lat_max - velez[0] < 0.095  # 10 km ≈ 0,09° de latitud


def test_parse_near_validates_values_and_radius():
    assert geo.parse_near({"near": "6.0139,-73.6736", "radio": "25"}) == ((6.01, -73.67), 25)
    assert geo.parse_near({"near": "6.0,-73.6", "radio": "999"})[1] == 10
    assert geo.parse_near({"near": "6.0,-73.6", "radio": "x"})[1] == 10
    assert geo.parse_near({"near": "malo"}) is None and geo.parse_near({}) is None


def test_listing_point_falls_back_from_listing_to_village_to_municipality(app):
    listing = Listing.query.first()
    listing.lat = listing.lng = None
    listing.village.lat = listing.village.lng = None
    point, exact = geo.listing_point(listing)
    assert point == (listing.municipality.lat, listing.municipality.lng) and not exact
    listing.village.lat, listing.village.lng = 6.1, -73.7
    assert geo.listing_point(listing) == ((6.1, -73.7), False)
    listing.lat, listing.lng = 6.02, -73.68
    assert geo.listing_point(listing) == ((6.02, -73.68), True)
    listing.municipality.lat = listing.municipality.lng = listing.village.lat = listing.village.lng = None
    listing.lat = listing.lng = None
    assert geo.listing_point(listing) == (None, False)


def test_listing_ids_near_uses_distance_not_just_the_box(app):
    velez = Municipality.query.filter_by(slug="velez").one()
    center = (velez.lat, velez.lng)
    near_ids = set(geo.listing_ids_near(center, 5))
    assert near_ids and all(Listing.query.get(i).municipality_id == velez.id for i in near_ids)
    barbosa_ids = {i for (i,) in Listing.query.with_entities(Listing.id).filter(
        Listing.municipality.has(slug="barbosa"))}  # fmt: skip
    assert barbosa_ids and not (near_ids & barbosa_ids)
    assert barbosa_ids <= set(geo.listing_ids_near(center, 25))
    village = Village.query.filter_by(municipality_id=velez.id).first()
    assert village is not None

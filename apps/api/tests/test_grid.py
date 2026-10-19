from decimal import Decimal

import pytest
from sqlalchemy import func, select
from weather_api.grid import InvalidCoordinate, normalize_to_grid
from weather_api.models import WeatherGridPoint

from .conftest import add_location


def test_snaps_to_nearest_tenth_degree_node():
    cell = normalize_to_grid(28.5384, -81.3789)
    assert (cell.latitude, cell.longitude) == (Decimal("28.5"), Decimal("-81.4"))
    assert cell.model_name == "weathernext_0p1"
    assert normalize_to_grid(28.54, -81.37).latitude == Decimal("28.5")
    assert normalize_to_grid(28.56, -81.37).latitude == Decimal("28.6")


def test_identifier_is_deterministic_and_wraps_the_dateline():
    assert normalize_to_grid(10, 180).identifier == normalize_to_grid(10, -180).identifier
    assert normalize_to_grid(10, 179.98).identifier == normalize_to_grid(10, -179.97).identifier
    assert normalize_to_grid(0, 0).identifier == "0:0"
    assert (
        normalize_to_grid(-33.87, 151.21).identifier == normalize_to_grid(-33.87, 151.21).identifier
    )
    assert normalize_to_grid(-0.04, -0.04).longitude == Decimal("0.0")


def test_halfway_points_round_consistently():
    assert normalize_to_grid(0.05, 0.05).identifier == "1:1"
    assert normalize_to_grid(-0.05, 0).lat_index == -1


@pytest.mark.parametrize("lat,lon", [(90.1, 0), (-90.1, 0), (0, 180.5), (0, -200)])
def test_rejects_invalid_coordinates(lat, lon):
    with pytest.raises(InvalidCoordinate):
        normalize_to_grid(lat, lon)


def test_nearby_locations_from_different_visitors_share_one_grid_point(
    client, other_client, session
):
    add_location(client, "Ben's Home", 28.51, -81.31)
    add_location(other_client, "User B's Home", 28.53, -81.28)
    add_location(other_client, "Office", 28.47, -81.33)

    assert session.scalar(select(func.count()).select_from(WeatherGridPoint)) == 1


def test_distant_locations_get_separate_grid_points(client, session):
    add_location(client, "Home", 28.5, -81.3)
    add_location(client, "Jackson Hole", 43.48, -110.76)
    assert session.scalar(select(func.count()).select_from(WeatherGridPoint)) == 2


def test_reusing_a_grid_point_reactivates_it(client, session):
    add_location(client, "Home", 28.5, -81.3)
    gp = session.scalars(select(WeatherGridPoint)).one()
    gp.active = False
    session.commit()
    add_location(client, "Neighbor", 28.52, -81.31)
    session.refresh(gp)
    assert gp.active is True


def test_offshore_grid_node_uses_the_locations_timezone(client, session):
    # Crescent Beach, FL: its grid node can fall over the Atlantic.
    add_location(client, "Crescent Beach", 29.7697, -81.2509)
    gp = session.scalars(select(WeatherGridPoint)).one()
    assert gp.timezone == "America/New_York"

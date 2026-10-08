from sqlalchemy import func, select
from weather_api.models import SavedLocation, WeatherGridPoint

from .conftest import add_location


def test_create_location_resolves_timezone_and_grid(client, session):
    loc = add_location(client, "Home", 28.5, -81.3)
    assert loc["name"] == "Home"
    assert loc["timezone"] == "America/New_York"
    assert loc["is_default"] is True
    assert "weather_grid_point_id" not in loc  # grid ids are internal

    gp = session.scalars(select(WeatherGridPoint)).one()
    assert float(gp.latitude) == 28.5
    assert float(gp.longitude) == -81.25
    assert gp.active is True


def test_location_survives_reload(client):
    add_location(client, "Home")
    # A "reload" is just another request carrying the same cookie.
    names = [loc["name"] for loc in client.get("/api/v1/locations").json()]
    assert names == ["Home"]


def test_only_first_location_is_default_and_default_can_move(client):
    home = add_location(client, "Home", 28.5, -81.3)
    lake = add_location(client, "Lake House", 43.48, -110.76)
    assert lake["is_default"] is False

    response = client.patch(f"/api/v1/locations/{lake['id']}", json={"is_default": True})
    assert response.status_code == 200
    by_name = {loc["name"]: loc for loc in client.get("/api/v1/locations").json()}
    assert by_name["Lake House"]["is_default"] is True
    assert by_name["Home"]["is_default"] is False
    # Default comes first in the list.
    assert client.get("/api/v1/locations").json()[0]["id"] == lake["id"]
    assert home["id"] != lake["id"]


def test_deleting_default_promotes_another(client):
    home = add_location(client, "Home")
    add_location(client, "Glacier", 48.76, -113.79)
    assert client.delete(f"/api/v1/locations/{home['id']}").status_code == 204
    remaining = client.get("/api/v1/locations").json()
    assert [loc["name"] for loc in remaining] == ["Glacier"]
    assert remaining[0]["is_default"] is True


def test_rename_location(client):
    loc = add_location(client, "Home")
    response = client.patch(f"/api/v1/locations/{loc['id']}", json={"name": "  Beach   House "})
    assert response.json()["name"] == "Beach House"


def test_coordinate_validation(client):
    client.get("/api/v1/me")
    for body in (
        {"name": "x", "latitude": 91, "longitude": 0},
        {"name": "x", "latitude": 0, "longitude": -181},
        {"name": "x", "latitude": "north", "longitude": 0},
        {"name": "   ", "latitude": 0, "longitude": 0},
        {"name": "x", "latitude": 0},
    ):
        response = client.post("/api/v1/locations", json=body)
        assert response.status_code == 422, body
        assert response.json()["error"]["code"] == "invalid_request"


def test_validation_errors_do_not_echo_coordinates(client):
    client.get("/api/v1/me")
    response = client.post(
        "/api/v1/locations", json={"name": "x", "latitude": 95.123456, "longitude": 0}
    )
    assert "95.123456" not in response.text


def test_visitor_id_in_body_is_rejected(client, other_client):
    other_client.get("/api/v1/me")
    client.get("/api/v1/me")
    response = client.post(
        "/api/v1/locations",
        json={
            "name": "x",
            "latitude": 1,
            "longitude": 1,
            "visitor_id": "00000000-0000-4000-8000-000000000000",
        },
    )
    assert response.status_code == 422


def test_location_limit(client, monkeypatch):
    from weather_api.config import get_settings

    monkeypatch.setattr(get_settings(), "max_locations_per_owner", 3)
    client.get("/api/v1/me")
    for i in range(3):
        response = client.post(
            "/api/v1/locations", json={"name": f"P{i}", "latitude": i * 10, "longitude": 10}
        )
        assert response.status_code == 201
    response = client.post(
        "/api/v1/locations", json={"name": "one more", "latitude": 1, "longitude": 1}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "too_many_locations"


def test_location_creation_is_rate_limited(client, monkeypatch):
    from weather_api.routes import locations

    monkeypatch.setattr(locations.create_limiter, "limit", 2)
    client.get("/api/v1/me")
    codes = [
        client.post(
            "/api/v1/locations", json={"name": "p", "latitude": i, "longitude": 1}
        ).status_code
        for i in range(3)
    ]
    assert codes == [201, 201, 429]


def test_locations_require_cookie_to_create(client, session):
    # Posting without a cookie creates a visitor on the fly (first contact).
    response = client.post(
        "/api/v1/locations", json={"name": "Home", "latitude": 28.5, "longitude": -81.3}
    )
    assert response.status_code == 201
    assert session.scalar(select(func.count()).select_from(SavedLocation)) == 1

from .conftest import add_location


def test_second_visitor_cannot_see_or_touch_first_visitors_location(client, other_client):
    home = add_location(client, "Home")
    other_client.get("/api/v1/me")

    assert other_client.get("/api/v1/locations").json() == []
    for method, path, kwargs in (
        ("GET", f"/api/v1/locations/{home['id']}/forecast", {}),
        ("GET", f"/api/v1/locations/{home['id']}/forecast-history", {}),
        ("PATCH", f"/api/v1/locations/{home['id']}", {"json": {"name": "Mine now"}}),
        ("DELETE", f"/api/v1/locations/{home['id']}", {}),
    ):
        response = other_client.request(method, path, **kwargs)
        # Indistinguishable from an id that doesn't exist.
        assert response.status_code == 404, (method, path)
        assert response.json()["error"]["code"] == "location_not_found"
        assert "28.5" not in response.text

    # Untouched for the owner.
    assert client.get("/api/v1/locations").json()[0]["name"] == "Home"


def test_no_cookie_cannot_access_location(client, app):
    from fastapi.testclient import TestClient

    home = add_location(client, "Home")
    with TestClient(app) as anonymous:
        assert anonymous.get(f"/api/v1/locations/{home['id']}/forecast").status_code == 404
        assert anonymous.delete(f"/api/v1/locations/{home['id']}").status_code == 404


def test_unknown_and_malformed_ids(client):
    client.get("/api/v1/me")
    assert (
        client.get("/api/v1/locations/00000000-0000-4000-8000-000000000000/forecast").status_code
        == 404
    )
    assert client.get("/api/v1/locations/not-a-uuid/forecast").status_code == 422

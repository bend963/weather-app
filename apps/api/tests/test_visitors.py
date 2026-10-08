import uuid

from sqlalchemy import func, select
from weather_api.models import Visitor
from weather_api.visitors import COOKIE_NAME, decode_cookie, encode_cookie

from .conftest import add_location


def test_first_visit_issues_opaque_signed_cookie(client):
    response = client.get("/api/v1/me")
    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"]
    assert f"{COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    assert "Max-Age=31536000" in set_cookie
    assert "Path=/" in set_cookie

    value = client.cookies[COOKIE_NAME]
    visitor_id, signature = value.split(".")
    uuid.UUID(visitor_id)  # an opaque UUID, nothing else
    assert signature

    body = response.json()
    assert body["visitor"]["kind"] == "anonymous"
    assert body["preferences"] == {
        "temperature_unit": "F",
        "precipitation_unit": "in",
        "wind_unit": "mph",
        "show_advanced_forecast": True,
    }
    assert body["location_count"] == 0


def test_visitor_persists_across_requests(client, session):
    client.get("/api/v1/me")
    first_cookie = client.cookies[COOKIE_NAME]
    add_location(client)
    second = client.get("/api/v1/me")
    assert second.json()["location_count"] == 1
    assert client.cookies[COOKIE_NAME] == first_cookie
    assert session.scalar(select(func.count()).select_from(Visitor)) == 1


def test_tampered_cookie_gets_a_fresh_visitor(client, session):
    client.get("/api/v1/me")
    add_location(client)
    real = client.cookies[COOKIE_NAME]
    visitor_id, _ = real.split(".")
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, f"{visitor_id}.forged-signature", domain="testserver.local")
    response = client.get("/api/v1/me")
    assert response.json()["location_count"] == 0
    assert client.cookies[COOKIE_NAME] != real


def test_unsigned_uuid_cookie_is_ignored(client):
    client.cookies.set(COOKIE_NAME, str(uuid.uuid4()), domain="testserver.local")
    assert client.get("/api/v1/locations").json() == []


def test_cookie_signature_roundtrip():
    vid = uuid.uuid4()
    assert decode_cookie(encode_cookie(vid, "secret"), "secret") == vid
    assert decode_cookie(encode_cookie(vid, "secret"), "other") is None
    assert decode_cookie("garbage", "secret") is None
    assert decode_cookie(None, "secret") is None


def test_read_endpoints_do_not_create_visitors(client, session):
    assert client.get("/api/v1/locations").json() == []
    assert COOKIE_NAME not in client.cookies
    assert session.scalar(select(func.count()).select_from(Visitor)) == 0


def test_update_preferences(client):
    client.get("/api/v1/me")
    response = client.patch(
        "/api/v1/me/preferences", json={"temperature_unit": "C", "wind_unit": "kmh"}
    )
    assert response.status_code == 200
    assert response.json()["temperature_unit"] == "C"
    assert client.get("/api/v1/me").json()["preferences"]["wind_unit"] == "kmh"
    assert client.patch("/api/v1/me/preferences", json={"temperature_unit": "K"}).status_code == 422

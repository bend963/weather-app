from datetime import timedelta

from fastapi.testclient import TestClient
from weather_api.forecast.providers import WeatherNextProvider, get_forecast_provider

from .conftest import FROZEN_NOW, TEST_PROVIDER, add_location


def test_new_location_gets_a_forecast(client):
    loc = add_location(client, "Home", 28.5, -81.3)
    response = client.get(f"/api/v1/locations/{loc['id']}/forecast")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["location"]["id"] == loc["id"]
    assert body["units"] == {"temperature": "F", "precipitation": "in", "wind": "mph"}

    run = body["model_run"]
    assert run["model"] == "mock_weathernext"
    assert run["initialization_time"].startswith("2026-10-08T00:00:00")

    assert body["current"]["source"] == "forecast"
    assert 30 < body["current"]["temperature"] < 110
    assert body["current"]["condition"]["label"]

    hourly = body["hourly"]
    assert len(hourly) == 72
    # Times are in the location's zone (EDT, UTC-4) and start at the current hour.
    assert hourly[0]["time"] == "2026-10-08T11:00:00-04:00"
    first = hourly[0]
    assert first["temperature"]["p10"] <= first["temperature"]["p50"] <= first["temperature"]["p90"]
    assert set(first["precip_exceedance"]) == {
        "trace",
        "0.01in",
        "0.10in",
        "0.25in",
        "0.50in",
        "1.00in",
    }
    assert first["confidence"]["level"] in {"high", "medium", "low"}

    daily = body["daily"]
    assert daily[0]["date"] == "2026-10-08"
    assert len(daily) >= 8
    day = daily[1]
    assert day["high"]["p50"] >= day["low"]["p50"]
    assert day["confidence"]["temperature_summary"]
    assert day["confidence"]["precipitation_summary"]
    # One high and low per member, in the same order every day.
    assert len(day["member_highs"]) == TEST_PROVIDER.members
    assert len(day["member_lows"]) == TEST_PROVIDER.members
    assert min(day["member_highs"]) <= day["high"]["p50"] <= max(day["member_highs"])
    for field in ("member_precip", "member_dewpoints", "member_feels_highs", "member_feels_lows"):
        assert len(day[field]) == TEST_PROVIDER.members
    assert sum(day["member_precip"]) / len(day["member_precip"]) >= 0

    assert body["rain_outlook"]["summary"]
    assert body["summary"]["members"] == TEST_PROVIDER.members


def test_units_follow_preferences(client):
    loc = add_location(client)
    f = client.get(f"/api/v1/locations/{loc['id']}/forecast").json()
    client.patch(
        "/api/v1/me/preferences", json={"temperature_unit": "C", "precipitation_unit": "mm"}
    )
    c = client.get(f"/api/v1/locations/{loc['id']}/forecast").json()
    assert c["units"]["temperature"] == "C"
    t_f = f["hourly"][0]["temperature"]["p50"]
    t_c = c["hourly"][0]["temperature"]["p50"]
    assert abs((t_c * 9 / 5 + 32) - t_f) < 0.2


def test_locations_in_one_grid_cell_share_one_forecast(client, other_client):
    a = add_location(client, "Ben's Home", 28.51, -81.31)
    b = add_location(other_client, "User B's Home", 28.55, -81.28)
    fa = client.get(f"/api/v1/locations/{a['id']}/forecast").json()
    fb = other_client.get(f"/api/v1/locations/{b['id']}/forecast").json()
    assert fa["model_run"]["id"] == fb["model_run"]["id"]
    assert fa["hourly"][5]["temperature"] == fb["hourly"][5]["temperature"]


def test_forecast_cache_headers_and_conditional_requests(client):
    loc = add_location(client)
    url = f"/api/v1/locations/{loc['id']}/forecast"
    first = client.get(url)
    assert first.headers["Cache-Control"].startswith("private, max-age=")
    etag = first.headers["ETag"]
    again = client.get(url, headers={"If-None-Match": etag})
    assert again.status_code == 304
    client.patch("/api/v1/me/preferences", json={"temperature_unit": "C"})
    assert client.get(url, headers={"If-None-Match": etag}).status_code == 200


def test_processing_state_before_any_forecast_exists(app, client):
    class Empty(type(TEST_PROVIDER)):  # type: ignore[misc]
        def latest_initializations(self, count=1, now=None):
            return []

    app.dependency_overrides[get_forecast_provider] = lambda: Empty()
    loc = add_location(client)
    response = client.get(f"/api/v1/locations/{loc['id']}/forecast")
    body = response.json()
    assert body["status"] == "processing"
    assert body["hourly"] == []
    assert response.headers["Cache-Control"] == "no-store"


def test_unavailable_state_when_weathernext_is_not_ready(app):
    app.dependency_overrides[get_forecast_provider] = lambda: WeatherNextProvider(None, None)
    with TestClient(app) as c:
        loc = add_location(c)
        body = c.get(f"/api/v1/locations/{loc['id']}/forecast").json()
    assert body["status"] == "unavailable"
    assert "Traceback" not in str(body)


def test_forecast_history_for_a_target_date(client):
    loc = add_location(client)  # backfills the last 3 runs (INGESTION_BACKFILL_RUNS=3)
    response = client.get(
        f"/api/v1/locations/{loc['id']}/forecast-history", params={"target_date": "2026-10-11"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["target_date"] == "2026-10-11"
    assert len(body["entries"]) == 3
    inits = [e["model_run"]["initialization_time"] for e in body["entries"]]
    assert inits == sorted(inits)
    leads = [e["lead_time_hours"] for e in body["entries"]]
    assert leads == sorted(leads, reverse=True)
    assert set(body["entries"][0]["values"]) == {"high", "low"}
    assert "2026-10-11" in body["available_dates"]

    rain = client.get(
        f"/api/v1/locations/{loc['id']}/forecast-history",
        params={"target_date": "2026-10-11", "metric": "precipitation"},
    ).json()
    assert rain["entries"][0]["values"]["precipitation"]["probability"] is not None


def test_forecast_history_for_a_target_time_uses_location_timezone(client):
    loc = add_location(client)
    body = client.get(
        f"/api/v1/locations/{loc['id']}/forecast-history",
        params={"target_time": "2026-10-10T18:00", "metric": "temperature"},
    ).json()
    # 18:00 in New York is 22:00 UTC.
    assert body["target_time"] == "2026-10-10T18:00:00-04:00"
    assert len(body["entries"]) == 3
    entry = body["entries"][-1]
    init = entry["model_run"]["initialization_time"]
    assert init.startswith("2026-10-08T00:00")
    assert entry["lead_time_hours"] == 70
    assert entry["values"]["temperature"]["p50"] is not None


def test_history_defaults_to_a_few_days_out(client):
    loc = add_location(client)
    body = client.get(f"/api/v1/locations/{loc['id']}/forecast-history").json()
    assert body["target_date"] > (FROZEN_NOW + timedelta(days=1)).date().isoformat()
    assert body["entries"]


def test_internal_errors_are_not_exposed(app, client, monkeypatch):
    from weather_api.forecast import read_model

    def explode(*args, **kwargs):
        raise RuntimeError("secret database detail")

    loc = add_location(client)
    monkeypatch.setattr(read_model, "latest_run_for_point", explode)
    with TestClient(app, raise_server_exceptions=False) as c:
        c.cookies = client.cookies
        response = c.get(f"/api/v1/locations/{loc['id']}/forecast")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret" not in response.text

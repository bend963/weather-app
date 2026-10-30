from datetime import UTC, datetime

import httpx
from weather_api.forecast.observations import (
    NwsObservations,
    Observation,
    Station,
    get_observation_source,
)

from .conftest import FROZEN_NOW, add_location

OBS_TIME = "2026-10-08T15:15:00+00:00"


def nws_latest(**overrides: object) -> dict:  # type: ignore[type-arg]
    props = {
        "timestamp": OBS_TIME,
        "textDescription": "Light Rain",
        "temperature": {"unitCode": "wmoUnit:degC", "value": 24.0},
        "dewpoint": {"unitCode": "wmoUnit:degC", "value": 21.0},
        "windDirection": {"unitCode": "wmoUnit:degree_(angle)", "value": 90},
        "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 18.0},
        "windGust": {"unitCode": "wmoUnit:km_h-1", "value": None},
        "relativeHumidity": {"unitCode": "wmoUnit:percent", "value": 83.1},
        "heatIndex": {"unitCode": "wmoUnit:degC", "value": 25.2},
        "windChill": {"unitCode": "wmoUnit:degC", "value": None},
        "precipitationLastHour": {"unitCode": "wmoUnit:m", "value": 0.0008},
        "cloudLayers": [{"amount": "SCT"}, {"amount": "OVC"}],
        "presentWeather": [{"intensity": "light", "weather": "rain"}],
    }
    props.update(overrides)
    return {"properties": props}


def nws_transport(latest: dict, calls: list[str] | None = None) -> httpx.MockTransport:  # type: ignore[type-arg]
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        path = request.url.path
        if path.startswith("/points/"):
            return httpx.Response(
                200,
                json={
                    "properties": {
                        "observationStations": "https://nws.test/gridpoints/MLB/26,68/stations"
                    }
                },
            )
        if path.endswith("/stations"):
            return httpx.Response(
                200,
                json={
                    "features": [
                        {
                            "geometry": {"coordinates": [-81.33, 28.43]},
                            "properties": {
                                "stationIdentifier": "KMCO",
                                "name": "Orlando International Airport",
                            },
                        },
                        {
                            "geometry": {"coordinates": [-75.0, 40.0]},
                            "properties": {"stationIdentifier": "KFAR", "name": "Far away"},
                        },
                    ]
                },
            )
        if path == "/stations/KMCO/observations/latest":
            return httpx.Response(200, json=latest)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_reads_the_nearest_station_and_converts_units():
    calls: list[str] = []
    nws = NwsObservations(
        "test", base_url="https://nws.test", transport=nws_transport(nws_latest(), calls)
    )
    obs = nws.latest(28.5, -81.3, FROZEN_NOW)
    assert obs is not None
    assert obs.station.id == "KMCO"
    assert 5 < obs.station.distance_km < 15
    assert obs.temperature_c == 24.0
    assert obs.wind_speed_mps == 5.0
    assert obs.wind_gust_mps is None
    assert obs.feels_like_c == 25.2
    assert obs.cloud_cover == 1.0
    assert obs.precip_last_hour_mm == 0.8
    assert obs.weather == (("rain", "light"),)
    # Cached: a second look makes no requests.
    before = len(calls)
    nws.latest(28.5, -81.3, FROZEN_NOW)
    assert len(calls) == before


def test_stale_or_missing_readings_fall_back():
    stale = nws_latest(timestamp="2026-10-08T12:00:00+00:00")
    nws = NwsObservations("test", base_url="https://nws.test", transport=nws_transport(stale))
    assert nws.latest(28.5, -81.3, FROZEN_NOW) is None

    no_temp = nws_latest(temperature={"unitCode": "wmoUnit:degC", "value": None})
    nws = NwsObservations("test", base_url="https://nws.test", transport=nws_transport(no_temp))
    assert nws.latest(28.5, -81.3, FROZEN_NOW) is None


def test_outside_the_us_and_errors_return_none():
    nws = NwsObservations(
        "test",
        base_url="https://nws.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(404)),
    )
    assert nws.latest(51.5, -0.1, FROZEN_NOW) is None

    nws = NwsObservations(
        "test",
        base_url="https://nws.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(503)),
    )
    assert nws.latest(28.5, -81.3, FROZEN_NOW) is None


class FakeSource:
    def latest(self, latitude: float, longitude: float, now: datetime) -> Observation | None:
        return Observation(
            station=Station("KMCO", "Orlando International Airport", 9.24),
            time=datetime(2026, 10, 8, 15, 15, tzinfo=UTC),
            description="Light Rain",
            temperature_c=24.0,
            dewpoint_c=21.0,
            humidity=None,
            wind_speed_mps=5.0,
            wind_direction_deg=90,
            wind_gust_mps=10.0,
            feels_like_c=None,
            cloud_cover=None,
            precip_last_hour_mm=0.8,
            weather=(("rain", "light"),),
        )


def test_forecast_uses_a_live_observation_for_now(app, client):
    app.dependency_overrides[get_observation_source] = lambda: FakeSource()
    loc = add_location(client)
    client.get(f"/api/v1/locations/{loc['id']}/forecast")  # starts the backfill
    response = client.get(f"/api/v1/locations/{loc['id']}/forecast")
    body = response.json()
    assert body["status"] == "ok"
    cur = body["current"]
    assert cur["source"] == "observation"
    assert cur["station"] == {
        "id": "KMCO",
        "name": "Orlando International Airport",
        "distance_km": 9.2,
    }
    assert cur["time"] == "2026-10-08T11:15:00-04:00"
    assert cur["temperature"] == 75.2  # 24 °C
    assert cur["wind_direction"] == "E"
    assert cur["wind_gust"] is not None
    assert cur["humidity"] == 83
    assert cur["condition"] == {"code": "rain", "label": "Light Rain"}
    assert response.headers["Cache-Control"] == "private, max-age=120"


def test_observation_time_is_part_of_the_etag(app, client):
    loc = add_location(client)
    client.get(f"/api/v1/locations/{loc['id']}/forecast")
    without = client.get(f"/api/v1/locations/{loc['id']}/forecast").headers["ETag"]
    app.dependency_overrides[get_observation_source] = lambda: FakeSource()
    with_obs = client.get(f"/api/v1/locations/{loc['id']}/forecast").headers["ETag"]
    assert without != with_obs

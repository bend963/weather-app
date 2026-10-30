"""Live current conditions from National Weather Service station observations.

The forecast can only estimate "now" from its nearest hour, and a WeatherNext
run is several hours old by the time it's published. NWS stations (mostly
airport ASOS/AWOS sites) report at least hourly, often every 5-20 minutes, and
the API is free and keyless. US locations only: elsewhere `/points` returns 404
and the app keeps the forecast estimate.

Flow: /points/{lat},{lon} names the nearby stations, nearest first (cached a
day per location). The latest observation of the first station with a fresh
temperature wins (cached a few minutes). Any failure returns None quickly, so
the forecast page never waits long on NWS.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Protocol

import httpx

from weather_api.cache import TTLCache
from weather_api.config import get_settings

log = logging.getLogger(__name__)

NWS_API = "https://api.weather.gov"
# An observation older than this isn't "now"; fall back to the forecast.
MAX_AGE = timedelta(minutes=90)
# Try a few stations: the nearest one sometimes reports no temperature.
STATIONS_TO_TRY = 3
# Ignore stations this far away; they don't describe the location.
MAX_STATION_KM = 60.0

# NWS sky cover codes as a fraction of the sky.
CLOUD_AMOUNTS = {
    "SKC": 0.0,
    "CLR": 0.0,
    "FEW": 0.19,
    "SCT": 0.44,
    "BKN": 0.75,
    "OVC": 1.0,
    "VV": 1.0,
}


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    distance_km: float


@dataclass(frozen=True)
class Observation:
    station: Station
    time: datetime
    description: str | None
    temperature_c: float
    dewpoint_c: float | None
    humidity: float | None
    wind_speed_mps: float | None
    wind_direction_deg: float | None
    wind_gust_mps: float | None
    feels_like_c: float | None
    cloud_cover: float | None
    precip_last_hour_mm: float | None
    # Present weather as NWS names it ("rain", "snow", "thunderstorms", "fog_mist"...),
    # with intensity ("light", "heavy" or None).
    weather: tuple[tuple[str, str | None], ...]


class ObservationSource(Protocol):
    def latest(self, latitude: float, longitude: float, now: datetime) -> Observation | None: ...


class NoObservations:
    """Used when live observations are turned off: the forecast estimate is shown."""

    def latest(self, latitude: float, longitude: float, now: datetime) -> Observation | None:
        return None


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rad = math.pi / 180
    a = (
        math.sin((lat2 - lat1) * rad / 2) ** 2
        + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin((lon2 - lon1) * rad / 2) ** 2
    )
    return 2 * 6371 * math.asin(math.sqrt(a))


def _value(props: dict[str, Any], key: str) -> float | None:
    """A QuantitativeValue in SI-ish units: degC, km_h-1 or m_s-1, percent, mm."""
    q = props.get(key) or {}
    v = q.get("value")
    if v is None:
        return None
    unit = q.get("unitCode", "")
    if unit.endswith("km_h-1"):
        return float(v) / 3.6
    if unit.endswith(":m"):  # precipitation is reported in metres
        return float(v) * 1000
    return float(v)


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_observation(station: Station, props: dict[str, Any]) -> Observation | None:
    temperature = _value(props, "temperature")
    stamp = props.get("timestamp")
    if temperature is None or not stamp:
        return None
    layers = props.get("cloudLayers") or []
    amounts = [
        CLOUD_AMOUNTS[layer["amount"]] for layer in layers if layer.get("amount") in CLOUD_AMOUNTS
    ]
    feels = _value(props, "heatIndex")
    if feels is None:
        feels = _value(props, "windChill")
    weather = tuple(
        (str(w["weather"]), w.get("intensity"))
        for w in props.get("presentWeather") or []
        if w.get("weather")
    )
    return Observation(
        station=station,
        time=_parse_time(stamp),
        description=props.get("textDescription") or None,
        temperature_c=temperature,
        dewpoint_c=_value(props, "dewpoint"),
        humidity=_value(props, "relativeHumidity"),
        wind_speed_mps=_value(props, "windSpeed"),
        wind_direction_deg=_value(props, "windDirection"),
        wind_gust_mps=_value(props, "windGust"),
        feels_like_c=feels,
        cloud_cover=max(amounts) if amounts else None,
        precip_last_hour_mm=_value(props, "precipitationLastHour"),
        weather=weather,
    )


class NwsObservations:
    def __init__(
        self,
        user_agent: str,
        *,
        base_url: str = NWS_API,
        timeout: float = 3.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"User-Agent": user_agent, "Accept": "application/geo+json"},
            timeout=timeout,
            transport=transport,
        )
        self._stations = TTLCache(max_entries=1024, ttl_seconds=24 * 3600)
        self._latest = TTLCache(max_entries=1024, ttl_seconds=5 * 60)
        # After a failure, leave NWS alone for a minute rather than slow every page.
        self._failures = TTLCache(max_entries=1024, ttl_seconds=60)

    def stations(self, latitude: float, longitude: float) -> list[Station]:
        key = (round(latitude, 3), round(longitude, 3))
        cached = self._stations.get(key)
        if cached is not None:
            return cached
        point = self._client.get(f"/points/{key[0]},{key[1]}")
        if point.status_code == 404:  # outside NWS coverage
            self._stations.set(key, [])
            return []
        point.raise_for_status()
        url = point.json()["properties"]["observationStations"]
        found = self._client.get(url, params={"limit": 10})
        found.raise_for_status()
        stations = []
        for f in found.json().get("features", []):
            lon, lat = f["geometry"]["coordinates"][:2]
            km = _distance_km(latitude, longitude, lat, lon)
            if km <= MAX_STATION_KM:
                p = f["properties"]
                stations.append(
                    Station(p["stationIdentifier"], p.get("name") or p["stationIdentifier"], km)
                )
        stations.sort(key=lambda s: s.distance_km)
        self._stations.set(key, stations)
        return stations

    def _station_latest(self, station: Station) -> Observation | None:
        cached = self._latest.get(station.id)
        if cached is not None:
            return cached or None
        r = self._client.get(f"/stations/{station.id}/observations/latest")
        obs = (
            parse_observation(station, r.json().get("properties", {}))
            if r.status_code == 200
            else None
        )
        self._latest.set(station.id, obs or False)
        return obs

    def latest(self, latitude: float, longitude: float, now: datetime) -> Observation | None:
        key = (round(latitude, 3), round(longitude, 3))
        if self._failures.get(key):
            return None
        try:
            for station in self.stations(latitude, longitude)[:STATIONS_TO_TRY]:
                obs = self._station_latest(station)
                if obs is not None and now - obs.time <= MAX_AGE:
                    return obs
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
            log.warning("NWS observations unavailable for %s: %s", key, e)
            self._failures.set(key, True)
        return None


@lru_cache
def _nws() -> NwsObservations:
    return NwsObservations(get_settings().nws_user_agent)


def get_observation_source() -> ObservationSource:
    """FastAPI dependency; tests override it."""
    if get_settings().current_conditions_source == "nws":
        return _nws()
    return NoObservations()

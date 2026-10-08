"""Location search behind a provider interface.

The frontend only talks to /api/v1/geocode/*, so the provider (Nominatim in
development, Google Places or Mapbox later) can change without frontend work.

Searched places are public; they are not saved locations and carry no owner.
Queries are not logged.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import httpx

from weather_api.config import get_settings

log = logging.getLogger(__name__)


class GeocodingUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Place:
    name: str
    label: str  # e.g. "Orlando, Florida, United States"
    latitude: float
    longitude: float
    country_code: str | None = None


class GeocodingProvider(Protocol):
    def search_locations(self, query: str, limit: int = 8) -> list[Place]: ...

    def reverse_geocode(self, latitude: float, longitude: float) -> Place | None: ...


class NominatimGeocoder:
    """OpenStreetMap Nominatim. Fine for development; its usage policy
    (1 request/second, identifying User-Agent) rules it out for production."""

    def __init__(self, base_url: str, user_agent: str, timeout: float = 5.0) -> None:
        self._client = httpx.Client(
            base_url=base_url, headers={"User-Agent": user_agent}, timeout=timeout
        )

    def _get(self, path: str, params: dict[str, str | int | float]) -> object:
        try:
            response = self._client.get(path, params={**params, "format": "jsonv2"})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            log.warning("geocoder request failed", extra={"error_category": type(exc).__name__})
            raise GeocodingUnavailable("Location search is unavailable") from exc

    @staticmethod
    def _place(item: dict) -> Place:  # type: ignore[type-arg]
        address = item.get("address") or {}
        name = item.get("name") or item.get("display_name", "").split(",")[0]
        return Place(
            name=name,
            label=item.get("display_name", name),
            latitude=float(item["lat"]),
            longitude=float(item["lon"]),
            country_code=(address.get("country_code") or "").upper() or None,
        )

    def search_locations(self, query: str, limit: int = 8) -> list[Place]:
        data = self._get("/search", {"q": query, "limit": limit, "addressdetails": 1})
        return [self._place(i) for i in data] if isinstance(data, list) else []

    def reverse_geocode(self, latitude: float, longitude: float) -> Place | None:
        data = self._get("/reverse", {"lat": latitude, "lon": longitude, "zoom": 10})
        if not isinstance(data, dict) or "lat" not in data:
            return None
        return self._place(data)


# A small offline gazetteer for tests, CI, E2E and offline development.
_STATIC_PLACES = [
    Place("Orlando", "Orlando, Florida, United States", 28.5384, -81.3789, "US"),
    Place("Crescent Beach", "Crescent Beach, Florida, United States", 29.7697, -81.2509, "US"),
    Place("Miami", "Miami, Florida, United States", 25.7617, -80.1918, "US"),
    Place("Tampa", "Tampa, Florida, United States", 27.9506, -82.4572, "US"),
    Place("Jacksonville", "Jacksonville, Florida, United States", 30.3322, -81.6557, "US"),
    Place("Atlanta", "Atlanta, Georgia, United States", 33.7490, -84.3880, "US"),
    Place("New York", "New York, New York, United States", 40.7128, -74.0060, "US"),
    Place("Boston", "Boston, Massachusetts, United States", 42.3601, -71.0589, "US"),
    Place("Washington", "Washington, District of Columbia, United States", 38.9072, -77.0369, "US"),
    Place("Chicago", "Chicago, Illinois, United States", 41.8781, -87.6298, "US"),
    Place("Denver", "Denver, Colorado, United States", 39.7392, -104.9903, "US"),
    Place("Jackson Hole", "Jackson, Wyoming, United States", 43.4799, -110.7624, "US"),
    Place("Glacier National Park", "Glacier National Park, Montana, United States", 48.7596, -113.7870, "US"),
    Place("Seattle", "Seattle, Washington, United States", 47.6062, -122.3321, "US"),
    Place("San Francisco", "San Francisco, California, United States", 37.7749, -122.4194, "US"),
    Place("Los Angeles", "Los Angeles, California, United States", 34.0522, -118.2437, "US"),
    Place("Phoenix", "Phoenix, Arizona, United States", 33.4484, -112.0740, "US"),
    Place("Austin", "Austin, Texas, United States", 30.2672, -97.7431, "US"),
    Place("Houston", "Houston, Texas, United States", 29.7604, -95.3698, "US"),
    Place("Dallas", "Dallas, Texas, United States", 32.7767, -96.7970, "US"),
    Place("New Orleans", "New Orleans, Louisiana, United States", 29.9511, -90.0715, "US"),
    Place("Nashville", "Nashville, Tennessee, United States", 36.1627, -86.7816, "US"),
    Place("Minneapolis", "Minneapolis, Minnesota, United States", 44.9778, -93.2650, "US"),
    Place("Salt Lake City", "Salt Lake City, Utah, United States", 40.7608, -111.8910, "US"),
    Place("Anchorage", "Anchorage, Alaska, United States", 61.2181, -149.9003, "US"),
    Place("Honolulu", "Honolulu, Hawaii, United States", 21.3069, -157.8583, "US"),
    Place("Toronto", "Toronto, Ontario, Canada", 43.6532, -79.3832, "CA"),
    Place("Vancouver", "Vancouver, British Columbia, Canada", 49.2827, -123.1207, "CA"),
    Place("London", "London, England, United Kingdom", 51.5074, -0.1278, "GB"),
    Place("Paris", "Paris, Île-de-France, France", 48.8566, 2.3522, "FR"),
    Place("Berlin", "Berlin, Germany", 52.5200, 13.4050, "DE"),
    Place("Zurich", "Zurich, Switzerland", 47.3769, 8.5417, "CH"),
    Place("Tokyo", "Tokyo, Japan", 35.6762, 139.6503, "JP"),
    Place("Sydney", "Sydney, New South Wales, Australia", -33.8688, 151.2093, "AU"),
    Place("Auckland", "Auckland, New Zealand", -36.8485, 174.7633, "NZ"),
    Place("Mexico City", "Mexico City, Mexico", 19.4326, -99.1332, "MX"),
    Place("São Paulo", "São Paulo, Brazil", -23.5505, -46.6333, "BR"),
    Place("Cape Town", "Cape Town, South Africa", -33.9249, 18.4241, "ZA"),
]  # fmt: skip


class StaticGeocoder:
    def search_locations(self, query: str, limit: int = 8) -> list[Place]:
        q = query.strip().lower()
        if not q:
            return []
        starts = [p for p in _STATIC_PLACES if p.name.lower().startswith(q)]
        contains = [p for p in _STATIC_PLACES if q in p.label.lower() and p not in starts]
        return (starts + contains)[:limit]

    def reverse_geocode(self, latitude: float, longitude: float) -> Place | None:
        nearest = min(
            _STATIC_PLACES,
            key=lambda p: (p.latitude - latitude) ** 2 + (p.longitude - longitude) ** 2,
        )
        # Only claim a name when reasonably close (~0.5°).
        if (nearest.latitude - latitude) ** 2 + (nearest.longitude - longitude) ** 2 > 0.25:
            return None
        return nearest


@lru_cache
def get_geocoder() -> GeocodingProvider:
    settings = get_settings()
    if settings.geocoder_provider == "static":
        return StaticGeocoder()
    return NominatimGeocoder(settings.nominatim_url, settings.nws_user_agent)

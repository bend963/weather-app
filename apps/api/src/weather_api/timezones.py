"""Resolve an IANA timezone for a coordinate, offline."""

from functools import lru_cache

from timezonefinder import TimezoneFinder


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    return TimezoneFinder()


def timezone_for(latitude: float, longitude: float) -> str:
    """IANA timezone name, e.g. "America/New_York".

    Over open ocean timezonefinder returns an "Etc/GMT±N" zone, which is still a
    valid IANA name; the final fallback is UTC.
    """
    name = _finder().timezone_at(lat=latitude, lng=longitude)
    return name or "UTC"

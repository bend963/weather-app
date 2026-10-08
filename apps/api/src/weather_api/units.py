"""Unit conversion. Everything is stored in SI; conversion happens only on output."""

from typing import Literal

TemperatureUnit = Literal["F", "C"]
PrecipitationUnit = Literal["in", "mm"]
WindUnit = Literal["mph", "kmh", "mps", "kt"]

MM_PER_INCH = 25.4


def convert_temperature(celsius: float | None, unit: TemperatureUnit) -> float | None:
    if celsius is None:
        return None
    if unit == "F":
        return round(celsius * 9 / 5 + 32, 1)
    return round(celsius, 1)


def convert_temperature_delta(delta_c: float | None, unit: TemperatureUnit) -> float | None:
    """Convert a temperature *difference* (no offset)."""
    if delta_c is None:
        return None
    return round(delta_c * 9 / 5, 1) if unit == "F" else round(delta_c, 1)


def convert_precipitation(mm: float | None, unit: PrecipitationUnit) -> float | None:
    if mm is None:
        return None
    if unit == "in":
        return round(mm / MM_PER_INCH, 2)
    return round(mm, 1)


_WIND_FACTORS: dict[str, float] = {"mps": 1.0, "mph": 2.236936, "kmh": 3.6, "kt": 1.943844}


def convert_wind(mps: float | None, unit: WindUnit) -> float | None:
    if mps is None:
        return None
    return round(mps * _WIND_FACTORS[unit], 1)


_CARDINALS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]  # fmt: skip


def cardinal_direction(degrees: float | None) -> str | None:
    """Meteorological direction (where the wind blows *from*) as a 16-point compass label."""
    if degrees is None:
        return None
    return _CARDINALS[int((degrees % 360) / 22.5 + 0.5) % 16]

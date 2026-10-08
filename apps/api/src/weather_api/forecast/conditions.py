"""Derived, human-facing weather quantities: sky condition and "feels like"."""

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Condition:
    code: str  # stable identifier the frontend maps to an icon
    label: str


def is_daytime(latitude: float, longitude: float, when: datetime) -> bool:
    """Whether the sun is above the horizon (NOAA low-precision solar position)."""
    day_of_year = when.timetuple().tm_yday
    hour_utc = when.hour + when.minute / 60
    gamma = 2 * math.pi / 365 * (day_of_year - 1 + (hour_utc - 12) / 24)
    declination = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
    )
    eq_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    solar_minutes = hour_utc * 60 + eq_time + 4 * longitude
    hour_angle = math.radians(solar_minutes / 4 - 180)
    lat = math.radians(latitude)
    cos_zenith = math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(
        declination
    ) * math.cos(hour_angle)
    return cos_zenith > -0.0145  # sun's upper limb at the horizon, with refraction


def sky_condition(
    *,
    cloud_cover: float | None,
    precip_probability: float | None,
    precip_amount_mm: float | None,
    temperature_c: float | None,
    daytime: bool = True,
    hours: int = 1,
) -> Condition:
    """Summarize a forecast period as one condition.

    precip_amount_mm is the median amount over the period, hours its length;
    rates are what distinguish rain from heavy rain.
    """
    pop = precip_probability or 0.0
    amount = precip_amount_mm or 0.0
    rate = amount / max(hours, 1)
    frozen = temperature_c is not None and temperature_c <= 0.5

    if pop >= 0.5 and amount >= 0.1:
        if frozen:
            return Condition("snow", "Snow")
        if rate >= 4.0:
            return Condition("heavy-rain", "Heavy rain")
        return Condition("rain", "Rain")
    if pop >= 0.3:
        return (
            Condition("chance-snow", "Chance of snow")
            if frozen
            else Condition("chance-rain", "Chance of showers")
        )

    cloud = cloud_cover if cloud_cover is not None else 0.5
    if cloud < 0.15:
        return Condition("clear-day", "Sunny") if daytime else Condition("clear-night", "Clear")
    if cloud < 0.4:
        return (
            Condition("mostly-clear-day", "Mostly sunny")
            if daytime
            else Condition("mostly-clear-night", "Mostly clear")
        )
    if cloud < 0.7:
        return (
            Condition("partly-cloudy-day", "Partly cloudy")
            if daytime
            else Condition("partly-cloudy-night", "Partly cloudy")
        )
    if cloud < 0.9:
        return Condition("mostly-cloudy", "Mostly cloudy")
    return Condition("cloudy", "Cloudy")


def relative_humidity(temperature_c: float, dewpoint_c: float) -> float:
    """Relative humidity (0–100) from the Magnus approximation."""
    a, b = 17.625, 243.04
    rh = 100 * math.exp(a * dewpoint_c / (b + dewpoint_c) - a * temperature_c / (b + temperature_c))
    return max(0.0, min(100.0, rh))


def feels_like(temperature_c: float, dewpoint_c: float | None, wind_mps: float | None) -> float:
    """Apparent temperature using the NWS heat index and wind chill formulas.

    Heat index applies at or above 80 °F; wind chill at or below 50 °F with wind
    above 3 mph. Between those the air temperature is used.
    """
    t_f = temperature_c * 9 / 5 + 32
    wind_mph = (wind_mps or 0.0) * 2.236936

    if t_f >= 80 and dewpoint_c is not None:
        rh = relative_humidity(temperature_c, dewpoint_c)
        # Rothfusz regression (NWS), valid for heat index >= 80 °F.
        hi = (
            -42.379
            + 2.04901523 * t_f
            + 10.14333127 * rh
            - 0.22475541 * t_f * rh
            - 0.00683783 * t_f**2
            - 0.05481717 * rh**2
            + 0.00122874 * t_f**2 * rh
            + 0.00085282 * t_f * rh**2
            - 0.00000199 * t_f**2 * rh**2
        )
        if rh < 13 and 80 <= t_f <= 112:
            hi -= ((13 - rh) / 4) * math.sqrt((17 - abs(t_f - 95)) / 17)
        elif rh > 85 and 80 <= t_f <= 87:
            hi += ((rh - 85) / 10) * ((87 - t_f) / 5)
        return (max(hi, t_f) - 32) * 5 / 9

    if t_f <= 50 and wind_mph > 3:
        wc = 35.74 + 0.6215 * t_f - 35.75 * wind_mph**0.16 + 0.4275 * t_f * wind_mph**0.16
        return (min(wc, t_f) - 32) * 5 / 9

    return temperature_c

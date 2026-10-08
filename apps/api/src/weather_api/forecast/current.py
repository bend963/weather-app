"""Current conditions.

WeatherNext is a forecast system; it does not observe the present. Until an
observation source exists (NWS observations, METAR, personal weather stations),
"now" is the forecast hour nearest the current time, and the response says so
via source="forecast". An observation-backed provider only has to implement
CurrentConditionsProvider; the API and frontend already handle either source.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from weather_api.forecast.read_model import HourlyPoint


@dataclass
class CurrentConditions:
    source: Literal["forecast", "observation"]
    time: datetime
    temperature_c: float
    dewpoint_c: float | None
    wind_speed_mps: float | None
    wind_direction_deg: float | None
    cloud_cover: float | None
    precip_probability: float | None


class CurrentConditionsProvider(Protocol):
    def current(self, hourly: list[HourlyPoint], now: datetime) -> CurrentConditions | None: ...


class NearestForecastHour:
    """Uses the forecast hour closest to now."""

    def current(self, hourly: list[HourlyPoint], now: datetime) -> CurrentConditions | None:
        if not hourly:
            return None
        nearest = min(hourly, key=lambda h: abs((h.forecast_time - now).total_seconds()))
        if abs((nearest.forecast_time - now).total_seconds()) > 3 * 3600:
            return None  # the run doesn't cover now; better to show nothing than stale data
        return CurrentConditions(
            source="forecast",
            time=nearest.forecast_time,
            temperature_c=nearest.temperature_p50_c,
            dewpoint_c=nearest.dewpoint_p50_c,
            wind_speed_mps=nearest.wind_speed_p50_mps,
            wind_direction_deg=nearest.wind_direction_deg,
            cloud_cover=nearest.cloud_cover_p50,
            precip_probability=nearest.precip_probability,
        )

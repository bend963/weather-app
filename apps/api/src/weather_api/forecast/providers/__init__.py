"""Forecast providers, selected by FORECAST_PROVIDER."""

from functools import lru_cache

from weather_api.config import get_settings
from weather_api.forecast.providers.base import (
    EnsembleForecast,
    ForecastProvider,
    GridPointRef,
    ProviderUnavailable,
)
from weather_api.forecast.providers.mock import MockForecastProvider
from weather_api.forecast.providers.weathernext import WeatherNextProvider

__all__ = [
    "EnsembleForecast",
    "ForecastProvider",
    "GridPointRef",
    "MockForecastProvider",
    "ProviderUnavailable",
    "WeatherNextProvider",
    "get_forecast_provider",
]


@lru_cache
def get_forecast_provider() -> ForecastProvider:
    settings = get_settings()
    if settings.forecast_provider == "weathernext":
        return WeatherNextProvider(
            project=settings.google_cloud_project,
            dataset=settings.weathernext_bigquery_dataset,
        )
    return MockForecastProvider()

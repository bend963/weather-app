"""Application settings, read from environment variables (see .env.example)."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/weather"

    # Which forecast source feeds the app. "mock" needs no credentials; "gefs"
    # (NOAA's public ensemble) needs no credentials either, only the gefs extra.
    forecast_provider: Literal["mock", "gefs", "weathernext"] = "mock"

    google_cloud_project: str | None = None
    weathernext_bigquery_dataset: str | None = None

    # How many of the most recent model runs the ingestion job keeps filled for
    # every active grid point. Older runs are never deleted; this only bounds
    # how far back a newly activated grid point is backfilled.
    ingestion_backfill_runs: int = Field(default=8, ge=1, le=60)

    # Grid points no saved location references are deactivated after this many days.
    grid_point_inactive_days: int = Field(default=14, ge=1)

    geocoder_provider: Literal["nominatim", "static"] = "nominatim"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    # NWS and Nominatim both require an identifying User-Agent with contact info.
    nws_user_agent: str = "weathernext-personal-weather-app (dev@example.com)"

    # Used to sign the anonymous visitor cookie so ids cannot be forged.
    cookie_secret: str = "dev-only-insecure-cookie-secret-change-me"
    cookie_secure: bool | None = None  # defaults to True in production

    # Comma-separated list of frontend origins allowed to call the API directly.
    cors_allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    max_locations_per_owner: int = 50
    location_create_rate_per_hour: int = 30
    search_rate_per_minute: int = 30

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @property
    def secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment == "production" and settings.cookie_secret.startswith("dev-only"):
        raise RuntimeError("COOKIE_SECRET must be set in production")
    return settings

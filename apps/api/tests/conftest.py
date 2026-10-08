"""Test fixtures. Tests run against a real PostgreSQL database.

TEST_DATABASE_URL defaults to a local "weather_test" database; CI provides one
via a Postgres service container. The schema is built with the real Alembic
migrations, so migrations are tested on every run.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/weather_test"
)
os.environ["ENVIRONMENT"] = "test"
os.environ["GEOCODER_PROVIDER"] = "static"
os.environ["FORECAST_PROVIDER"] = "mock"
os.environ["INGESTION_BACKFILL_RUNS"] = "3"

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from weather_api.app import create_app  # noqa: E402
from weather_api.cache import forecast_cache  # noqa: E402
from weather_api.clock import get_now  # noqa: E402
from weather_api.db import get_engine  # noqa: E402
from weather_api.forecast.providers import MockForecastProvider, get_forecast_provider  # noqa: E402
from weather_api.routes import geocode, locations  # noqa: E402

API_DIR = Path(__file__).resolve().parents[1]
FROZEN_NOW = datetime(2026, 10, 8, 15, 30, tzinfo=UTC)

# Small horizon and ensemble keep tests fast while exercising the same code.
TEST_PROVIDER = MockForecastProvider(members=20, horizon_hours=240)


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> Iterator[None]:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    config = Config(str(API_DIR / "alembic.ini"))
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "TRUNCATE hourly_forecasts, daily_forecasts, forecast_runs, saved_locations, "
                "weather_grid_points, visitor_preferences, visitors, users CASCADE"
            )
        )
    forecast_cache.clear()
    locations.create_limiter.reset()
    geocode.search_limiter.reset()


@pytest.fixture
def session() -> Iterator[Session]:
    with Session(get_engine(), expire_on_commit=False) as s:
        yield s


@pytest.fixture
def provider() -> MockForecastProvider:
    return TEST_PROVIDER


@pytest.fixture
def app():  # type: ignore[no-untyped-def]
    application = create_app()
    application.dependency_overrides[get_now] = lambda: FROZEN_NOW
    application.dependency_overrides[get_forecast_provider] = lambda: TEST_PROVIDER
    return application


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with TestClient(app) as c:
        yield c


@pytest.fixture
def other_client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    """A second, unrelated browser."""
    with TestClient(app) as c:
        yield c


def add_location(
    client: TestClient, name: str = "Home", lat: float = 28.5, lon: float = -81.3
) -> dict:  # type: ignore[type-arg]
    client.get("/api/v1/me")
    response = client.post(
        "/api/v1/locations", json={"name": name, "latitude": lat, "longitude": lon}
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]

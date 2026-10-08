from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from weather_api.forecast.ingestion import deactivate_unused_grid_points, ingest_run, run_ingestion
from weather_api.forecast.providers import MockForecastProvider, ProviderUnavailable
from weather_api.locations import get_or_create_grid_point
from weather_api.models import (
    DailyForecast,
    ForecastRun,
    HourlyForecast,
    SavedLocation,
    Visitor,
    WeatherGridPoint,
)

from .conftest import FROZEN_NOW

PROVIDER = MockForecastProvider(members=10, horizon_hours=72)


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


@pytest.fixture
def grid_points(session):
    points = [
        get_or_create_grid_point(session, 28.5, -81.3),
        get_or_create_grid_point(session, 43.48, -110.76),
    ]
    session.commit()
    return points


def test_ingestion_writes_hourly_and_daily_rows(session, grid_points):
    report = run_ingestion(session, PROVIDER, backfill_runs=1, now=FROZEN_NOW)
    assert [r.status for r in report.runs] == ["complete"]
    assert report.runs[0].points_ingested == 2
    assert count(session, HourlyForecast) == 2 * 73
    assert count(session, DailyForecast) > 0

    run = session.scalars(select(ForecastRun)).one()
    assert run.status == "complete"
    assert run.completed_at is not None
    assert run.model == "mock_weathernext"
    assert run.source_metadata["synthetic"] is True


def test_ingestion_is_idempotent(session, grid_points):
    run_ingestion(session, PROVIDER, backfill_runs=2, now=FROZEN_NOW)
    hourly, daily, runs = (
        count(session, HourlyForecast),
        count(session, DailyForecast),
        count(session, ForecastRun),
    )
    second = run_ingestion(session, PROVIDER, backfill_runs=2, now=FROZEN_NOW)
    assert all(r.skipped for r in second.runs)
    assert (
        count(session, HourlyForecast),
        count(session, DailyForecast),
        count(session, ForecastRun),
    ) == (
        hourly,
        daily,
        runs,
    )


def test_new_runs_never_overwrite_history(session, grid_points):
    run_ingestion(session, PROVIDER, backfill_runs=1, now=FROZEN_NOW)
    first_run = session.scalars(select(ForecastRun)).one()
    before = {
        (h.weather_grid_point_id, h.forecast_time): h.temperature_p50_c
        for h in session.scalars(select(HourlyForecast))
    }

    later = FROZEN_NOW + timedelta(hours=12)
    run_ingestion(session, PROVIDER, backfill_runs=1, now=later)
    assert count(session, ForecastRun) == 2
    after_first_run = {
        (h.weather_grid_point_id, h.forecast_time): h.temperature_p50_c
        for h in session.scalars(
            select(HourlyForecast).where(HourlyForecast.forecast_run_id == first_run.id)
        )
    }
    assert after_first_run == before

    # The same target hour now has a prediction from each run.
    target = first_run.initialization_time + timedelta(hours=36)
    predictions = session.scalars(
        select(HourlyForecast).where(
            HourlyForecast.weather_grid_point_id == grid_points[0].id,
            HourlyForecast.forecast_time == target,
        )
    ).all()
    assert sorted(p.lead_time_hours for p in predictions) == [24, 36]


def test_only_active_grid_points_are_ingested(session, grid_points):
    grid_points[1].active = False
    session.commit()
    report = run_ingestion(session, PROVIDER, backfill_runs=1, now=FROZEN_NOW)
    assert report.runs[0].points_ingested == 1
    ingested = set(session.scalars(select(HourlyForecast.weather_grid_point_id).distinct()))
    assert ingested == {grid_points[0].id}


def test_new_point_is_backfilled_into_completed_runs(session, grid_points):
    run_ingestion(session, PROVIDER, backfill_runs=2, now=FROZEN_NOW)
    new_point = get_or_create_grid_point(session, -33.87, 151.21)
    session.commit()

    report = run_ingestion(
        session, PROVIDER, backfill_runs=2, now=FROZEN_NOW, grid_point_ids=[new_point.id]
    )
    assert [r.points_ingested for r in report.runs] == [1, 1]
    runs_with_point = session.scalar(
        select(func.count(func.distinct(HourlyForecast.forecast_run_id))).where(
            HourlyForecast.weather_grid_point_id == new_point.id
        )
    )
    assert runs_with_point == 2
    assert {r.status for r in session.scalars(select(ForecastRun))} == {"complete"}


def test_provider_failure_marks_run_failed_and_retries_later(session, grid_points):
    class Broken(MockForecastProvider):
        def get_forecast(self, grid_points, initialization_time=None):
            raise ProviderUnavailable("down")

    broken = Broken(members=5, horizon_hours=24)
    init = broken.latest_initializations(1, now=FROZEN_NOW)[0]
    report = ingest_run(session, broken, init)
    assert report.status == "failed"
    assert report.error_category == "provider_unavailable"
    run = session.scalars(select(ForecastRun)).one()
    assert run.status == "failed"
    assert run.source_metadata["error_category"] == "provider_unavailable"
    assert count(session, HourlyForecast) == 0

    # The same run succeeds on the next attempt.
    healthy = MockForecastProvider(members=5, horizon_hours=24)
    assert ingest_run(session, healthy, init).status == "complete"
    session.refresh(run)
    assert run.status == "complete"


def test_unused_grid_points_are_deactivated_after_grace_period(session, grid_points):
    visitor = Visitor()
    session.add(visitor)
    session.flush()
    session.add(
        SavedLocation(
            visitor_id=visitor.id,
            weather_grid_point_id=grid_points[0].id,
            name="Home",
            latitude=28.5,
            longitude=-81.3,
            timezone="America/New_York",
        )
    )
    session.commit()

    assert deactivate_unused_grid_points(session, 14, now=datetime.now(UTC)) == 0
    assert (
        deactivate_unused_grid_points(session, 14, now=datetime.now(UTC) + timedelta(days=15)) == 1
    )
    session.refresh(grid_points[0])
    session.refresh(grid_points[1])
    assert grid_points[0].active is True  # referenced by a saved location
    assert grid_points[1].active is False
    assert count(session, WeatherGridPoint) == 2  # deactivated, not deleted

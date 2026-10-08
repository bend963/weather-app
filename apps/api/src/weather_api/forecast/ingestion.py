"""Forecast ingestion: provider members -> hourly_forecasts + daily_forecasts.

Flow for each model initialization (newest first, within the backfill window):

    ensure forecast_runs row (model, initialization_time)
    find active grid points with no rows in this run yet
    if none and the run is complete: nothing to do
    fetch members from the provider in batches
    compute ensemble statistics, insert hourly + daily rows
    mark the run complete

Idempotency comes from the database, not from bookkeeping: every insert uses
ON CONFLICT DO NOTHING against the (grid point, run, time/date) unique keys,
and "already processed" means "rows exist". Running the job twice, or the API
backfilling a new grid point while the scheduled job runs, cannot duplicate or
overwrite anything. Previous runs are never modified, so forecast history is
preserved by construction.

One grid point's hourly and daily rows for a run are written in one
transaction, so a point is either fully present in a run or absent.
"""

import logging
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from weather_api.forecast.ensemble import daily_statistics, hourly_statistics
from weather_api.forecast.providers import ForecastProvider, GridPointRef, ProviderUnavailable
from weather_api.models import (
    DailyForecast,
    ForecastRun,
    HourlyForecast,
    SavedLocation,
    WeatherGridPoint,
)

log = logging.getLogger(__name__)

BATCH_SIZE = 100


@dataclass
class RunReport:
    initialization_time: datetime
    run_id: UUID | None = None
    points_ingested: int = 0
    skipped: bool = False
    status: str = "pending"
    error_category: str | None = None


@dataclass
class IngestionReport:
    runs: list[RunReport] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(r.status == "failed" for r in self.runs)

    def as_dict(self) -> dict[str, object]:
        return {
            "runs": [
                {**asdict(r), "initialization_time": r.initialization_time.isoformat()}
                for r in self.runs
            ]
        }


def run_ingestion(
    session: Session,
    provider: ForecastProvider,
    *,
    backfill_runs: int = 1,
    now: datetime | None = None,
    grid_point_ids: Sequence[UUID] | None = None,
) -> IngestionReport:
    """Make sure the latest `backfill_runs` initializations are ingested.

    With grid_point_ids, only those points are considered (used by the API to
    fill a newly saved location immediately); otherwise all active points.
    """
    report = IngestionReport()
    inits = provider.latest_initializations(backfill_runs, now=now)
    # Newest first: a freshly saved location shows the current run as soon as
    # possible, and older runs (history) fill in behind it.
    for init in sorted(inits, reverse=True):
        report.runs.append(ingest_run(session, provider, init, grid_point_ids=grid_point_ids))
    return report


def ingest_run(
    session: Session,
    provider: ForecastProvider,
    initialization_time: datetime,
    *,
    grid_point_ids: Sequence[UUID] | None = None,
) -> RunReport:
    started = time.monotonic()
    report = RunReport(initialization_time=initialization_time)
    run = _get_or_create_run(session, provider, initialization_time)
    report.run_id = run.id

    pending = _points_missing_from_run(session, run.id, grid_point_ids)
    if not pending:
        if run.status != "complete" and grid_point_ids is None:
            _set_status(session, run.id, "complete")
        session.commit()
        report.skipped = True
        report.status = "complete" if grid_point_ids is None else run.status
        log.info(
            "forecast run already processed",
            extra={"forecast_run_id": str(run.id), "provider": provider.model_name},
        )
        return report

    if run.status != "complete":
        _set_status(session, run.id, "processing")
        session.commit()

    try:
        for batch in _batched(pending, BATCH_SIZE):
            forecasts = provider.get_forecast(batch, initialization_time)
            for gp in batch:
                fc = forecasts.get(gp.id)
                if fc is None:
                    continue
                _write_point(session, run.id, gp, fc)
                report.points_ingested += 1
            session.commit()
    except Exception as exc:
        session.rollback()
        report.status = "failed"
        report.error_category = (
            "provider_unavailable" if isinstance(exc, ProviderUnavailable) else type(exc).__name__
        )
        _set_status(session, run.id, "failed", error_category=report.error_category)
        session.commit()
        log.exception(
            "forecast run failed",
            extra={
                "forecast_run_id": str(run.id),
                "provider": provider.model_name,
                "error_category": report.error_category,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
        return report

    # A run is complete once every active point is in it. A targeted backfill
    # of one point doesn't get to declare that.
    if grid_point_ids is None:
        _set_status(session, run.id, "complete", points=report.points_ingested)
        report.status = "complete"
    else:
        report.status = run.status
    session.commit()
    log.info(
        "forecast run ingested",
        extra={
            "forecast_run_id": str(run.id),
            "provider": provider.model_name,
            "points": report.points_ingested,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "status": report.status,
        },
    )
    return report


def deactivate_unused_grid_points(
    session: Session, inactive_days: int, now: datetime | None = None
) -> int:
    """Stop ingesting grid points no saved location references any more.

    The grace period avoids churn when someone deletes and re-adds a place.
    Forecast rows for deactivated points are kept as history.
    """
    cutoff = (now or datetime.now(UTC)) - timedelta(days=inactive_days)
    referenced = exists().where(SavedLocation.weather_grid_point_id == WeatherGridPoint.id)
    result = session.execute(
        update(WeatherGridPoint)
        .where(WeatherGridPoint.active, ~referenced, WeatherGridPoint.last_requested_at < cutoff)
        .values(active=False)
    )
    session.commit()
    return result.rowcount or 0  # type: ignore[attr-defined]


# --- internals ---------------------------------------------------------------


def _get_or_create_run(
    session: Session, provider: ForecastProvider, initialization_time: datetime
) -> ForecastRun:
    session.execute(
        insert(ForecastRun)
        .values(
            model=provider.model_name,
            initialization_time=initialization_time,
            forecast_horizon_hours=provider.horizon_hours,
            status="pending",
            source_metadata=provider.describe(),
        )
        .on_conflict_do_nothing(constraint="uq_forecast_runs_model_init")
    )
    run = session.scalars(
        select(ForecastRun).where(
            ForecastRun.model == provider.model_name,
            ForecastRun.initialization_time == initialization_time,
        )
    ).one()
    session.commit()
    return run


def _points_missing_from_run(
    session: Session, run_id: UUID, grid_point_ids: Sequence[UUID] | None
) -> list[GridPointRef]:
    has_rows = exists().where(
        HourlyForecast.forecast_run_id == run_id,
        HourlyForecast.weather_grid_point_id == WeatherGridPoint.id,
    )
    query = select(WeatherGridPoint).where(~has_rows)
    if grid_point_ids is None:
        query = query.where(WeatherGridPoint.active)
    else:
        query = query.where(WeatherGridPoint.id.in_(grid_point_ids))
    return [
        GridPointRef(
            id=gp.id,
            model_grid_identifier=gp.model_grid_identifier,
            latitude=float(gp.latitude),
            longitude=float(gp.longitude),
            timezone=gp.timezone,
        )
        for gp in session.scalars(query.order_by(WeatherGridPoint.id))
    ]


def _write_point(session: Session, run_id: UUID, gp: GridPointRef, fc) -> None:  # type: ignore[no-untyped-def]
    hourly = [
        {**asdict(row), "weather_grid_point_id": gp.id, "forecast_run_id": run_id}
        for row in hourly_statistics(fc)
    ]
    daily = [
        {**asdict(row), "weather_grid_point_id": gp.id, "forecast_run_id": run_id}
        for row in daily_statistics(fc, gp.timezone)
    ]
    session.execute(
        insert(HourlyForecast).on_conflict_do_nothing(constraint="uq_hourly_point_run_time"),
        hourly,
    )
    if daily:
        session.execute(
            insert(DailyForecast).on_conflict_do_nothing(constraint="uq_daily_point_run_date"),
            daily,
        )


def _set_status(session: Session, run_id: UUID, status: str, **metadata: object) -> None:
    values: dict[str, object] = {"status": status}
    if status == "complete":
        values["completed_at"] = func.now()
    if metadata:
        values["source_metadata"] = ForecastRun.source_metadata.op("||")(
            func.jsonb_build_object(*[x for kv in metadata.items() for x in kv])
        )
    session.execute(update(ForecastRun).where(ForecastRun.id == run_id).values(**values))


def _batched(items: Sequence[GridPointRef], size: int) -> Iterable[list[GridPointRef]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])

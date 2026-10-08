"""Read side: load a grid point's forecast for one run, in SI units."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from weather_api.cache import forecast_cache
from weather_api.models import DailyForecast, ForecastRun, HourlyForecast


@dataclass(frozen=True)
class RunInfo:
    id: UUID
    model: str
    initialization_time: datetime
    ingested_at: datetime
    completed_at: datetime | None
    forecast_horizon_hours: int
    status: str


@dataclass(frozen=True)
class HourlyPoint:
    forecast_time: datetime
    lead_time_hours: int
    temperature_p10_c: float | None
    temperature_p50_c: float
    temperature_p90_c: float | None
    dewpoint_p50_c: float | None
    wind_speed_p50_mps: float | None
    wind_speed_p90_mps: float | None
    wind_direction_deg: float | None
    precip_probability: float | None
    precip_p50_mm: float | None
    precip_p90_mm: float | None
    cloud_cover_p50: float | None
    confidence_score: float | None
    raw_summary: dict[str, Any]


@dataclass(frozen=True)
class DailyPoint:
    local_date: date
    high_p10_c: float | None
    high_p50_c: float
    high_p90_c: float | None
    low_p10_c: float | None
    low_p50_c: float
    low_p90_c: float | None
    precip_probability: float | None
    precip_p50_mm: float | None
    precip_p90_mm: float | None
    wind_max_p50_mps: float | None
    wind_max_p90_mps: float | None
    confidence_score: float | None
    temperature_agreement: float | None
    precip_agreement: float | None
    raw_summary: dict[str, Any]


@dataclass(frozen=True)
class GridForecast:
    run: RunInfo
    hourly: list[HourlyPoint]
    daily: list[DailyPoint]


def _run_info(run: ForecastRun) -> RunInfo:
    return RunInfo(
        id=run.id,
        model=run.model,
        initialization_time=run.initialization_time,
        ingested_at=run.ingested_at,
        completed_at=run.completed_at,
        forecast_horizon_hours=run.forecast_horizon_hours,
        status=run.status,
    )


def latest_run_for_point(session: Session, grid_point_id: UUID, model: str) -> RunInfo | None:
    """Newest run that contains this grid point.

    A point's rows for a run are written atomically, so if any exist the
    point's forecast for that run is complete, even while the run as a whole
    is still processing other points.
    """
    has_point = exists().where(
        HourlyForecast.forecast_run_id == ForecastRun.id,
        HourlyForecast.weather_grid_point_id == grid_point_id,
    )
    run = session.scalars(
        select(ForecastRun)
        .where(ForecastRun.model == model, ForecastRun.status != "failed", has_point)
        .order_by(ForecastRun.initialization_time.desc())
        .limit(1)
    ).first()
    return _run_info(run) if run else None


def load_grid_forecast(session: Session, grid_point_id: UUID, run: RunInfo) -> GridForecast:
    key = ("grid_forecast", grid_point_id, run.id)
    cached = forecast_cache.get(key)
    if cached is not None:
        return cached  # type: ignore[no-any-return]

    hourly = [
        load_hourly_point(h)
        for h in session.scalars(
            select(HourlyForecast)
            .where(
                HourlyForecast.weather_grid_point_id == grid_point_id,
                HourlyForecast.forecast_run_id == run.id,
            )
            .order_by(HourlyForecast.forecast_time)
        )
    ]
    daily = [
        load_daily_point(d)
        for d in session.scalars(
            select(DailyForecast)
            .where(
                DailyForecast.weather_grid_point_id == grid_point_id,
                DailyForecast.forecast_run_id == run.id,
            )
            .order_by(DailyForecast.local_date)
        )
    ]
    result = GridForecast(run=run, hourly=hourly, daily=daily)
    forecast_cache.set(key, result)
    return result


@dataclass(frozen=True)
class HistoryEntry:
    run: RunInfo
    lead_time_hours: int | None
    hourly: HourlyPoint | None = None
    daily: DailyPoint | None = None


def hourly_history(
    session: Session, grid_point_id: UUID, model: str, target_time: datetime
) -> list[HistoryEntry]:
    """Every run's forecast for one target hour, oldest run first."""
    rows = session.execute(
        select(ForecastRun, HourlyForecast)
        .join(HourlyForecast, HourlyForecast.forecast_run_id == ForecastRun.id)
        .where(
            ForecastRun.model == model,
            HourlyForecast.weather_grid_point_id == grid_point_id,
            HourlyForecast.forecast_time == target_time,
        )
        .order_by(ForecastRun.initialization_time)
    ).all()
    return [
        HistoryEntry(
            run=_run_info(run), lead_time_hours=h.lead_time_hours, hourly=load_hourly_point(h)
        )
        for run, h in rows
    ]


def daily_history(
    session: Session, grid_point_id: UUID, model: str, target_date: date
) -> list[HistoryEntry]:
    rows = session.execute(
        select(ForecastRun, DailyForecast)
        .join(DailyForecast, DailyForecast.forecast_run_id == ForecastRun.id)
        .where(
            ForecastRun.model == model,
            DailyForecast.weather_grid_point_id == grid_point_id,
            DailyForecast.local_date == target_date,
        )
        .order_by(ForecastRun.initialization_time)
    ).all()
    return [
        HistoryEntry(run=_run_info(run), lead_time_hours=None, daily=load_daily_point(d))
        for run, d in rows
    ]


def load_hourly_point(h: HourlyForecast) -> HourlyPoint:
    return HourlyPoint(
        forecast_time=h.forecast_time,
        lead_time_hours=h.lead_time_hours,
        temperature_p10_c=h.temperature_p10_c,
        temperature_p50_c=h.temperature_p50_c,
        temperature_p90_c=h.temperature_p90_c,
        dewpoint_p50_c=h.dewpoint_p50_c,
        wind_speed_p50_mps=h.wind_speed_p50_mps,
        wind_speed_p90_mps=h.wind_speed_p90_mps,
        wind_direction_deg=h.wind_direction_deg,
        precip_probability=h.precip_probability,
        precip_p50_mm=h.precip_p50_mm,
        precip_p90_mm=h.precip_p90_mm,
        cloud_cover_p50=h.cloud_cover_p50,
        confidence_score=h.confidence_score,
        raw_summary=h.raw_summary or {},
    )


def load_daily_point(d: DailyForecast) -> DailyPoint:
    return DailyPoint(
        local_date=d.local_date,
        high_p10_c=d.high_p10_c,
        high_p50_c=d.high_p50_c,
        high_p90_c=d.high_p90_c,
        low_p10_c=d.low_p10_c,
        low_p50_c=d.low_p50_c,
        low_p90_c=d.low_p90_c,
        precip_probability=d.precip_probability,
        precip_p50_mm=d.precip_p50_mm,
        precip_p90_mm=d.precip_p90_mm,
        wind_max_p50_mps=d.wind_max_p50_mps,
        wind_max_p90_mps=d.wind_max_p90_mps,
        confidence_score=d.confidence_score,
        temperature_agreement=d.temperature_agreement,
        precip_agreement=d.precip_agreement,
        raw_summary=d.raw_summary or {},
    )

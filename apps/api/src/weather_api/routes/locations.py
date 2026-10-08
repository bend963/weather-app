import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response, status
from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from weather_api import schemas
from weather_api.clock import get_now
from weather_api.config import Settings, get_settings
from weather_api.db import get_db
from weather_api.errors import ApiError, not_found
from weather_api.forecast import read_model
from weather_api.forecast.backfill import ensure_point_forecast
from weather_api.forecast.presenter import (
    ForecastPresenter,
    Presentation,
    model_run,
    select_days,
    select_hours,
)
from weather_api.forecast.providers import ForecastProvider, get_forecast_provider
from weather_api.locations import (
    create_location,
    delete_location,
    get_location,
    list_locations,
    mark_grid_point_requested,
    update_location,
)
from weather_api.models import DailyForecast, ForecastRun, SavedLocation, Visitor
from weather_api.ratelimit import RateLimiter
from weather_api.units import convert_precipitation, convert_temperature, convert_wind
from weather_api.visitors import Owner, current_visitor, optional_visitor, visitor_preferences

router = APIRouter(prefix="/api/v1/locations", tags=["locations"])

create_limiter = RateLimiter(get_settings().location_create_rate_per_hour, 3600)


def _location(loc: SavedLocation) -> schemas.Location:
    return schemas.Location.model_validate(loc)


def _owner(visitor: Visitor | None) -> Owner:
    if visitor is None:
        # No identity means nothing can be owned; report "not found", not 401,
        # so the existence of other people's ids is never revealed.
        raise not_found()
    return Owner(visitor_id=visitor.id)


@router.get("", response_model=list[schemas.Location])
def get_locations(
    visitor: Visitor | None = Depends(optional_visitor), session: Session = Depends(get_db)
) -> list[schemas.Location]:
    if visitor is None:
        return []
    return [_location(loc) for loc in list_locations(session, Owner(visitor_id=visitor.id))]


@router.post("", response_model=schemas.Location, status_code=status.HTTP_201_CREATED)
def post_location(
    body: schemas.LocationCreate,
    background: BackgroundTasks,
    visitor: Visitor = Depends(current_visitor),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider: ForecastProvider = Depends(get_forecast_provider),
    now: datetime = Depends(get_now),
) -> schemas.Location:
    create_limiter.check(str(visitor.id))
    location = create_location(
        session,
        Owner(visitor_id=visitor.id),
        name=body.name,
        latitude=body.latitude,
        longitude=body.longitude,
        max_locations=settings.max_locations_per_owner,
    )
    # Forecasts are per grid point; if this cell is new, fill it now rather
    # than waiting for the next scheduled ingestion.
    background.add_task(ensure_point_forecast, location.weather_grid_point_id, provider, now)
    return _location(location)


@router.patch("/{location_id}", response_model=schemas.Location)
def patch_location(
    location_id: UUID,
    body: schemas.LocationUpdate,
    visitor: Visitor | None = Depends(optional_visitor),
    session: Session = Depends(get_db),
) -> schemas.Location:
    location = update_location(
        session, _owner(visitor), location_id, name=body.name, is_default=body.is_default
    )
    return _location(location)


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_location(
    location_id: UUID,
    visitor: Visitor | None = Depends(optional_visitor),
    session: Session = Depends(get_db),
) -> Response:
    delete_location(session, _owner(visitor), location_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _presentation(session: Session, visitor: Visitor, location: SavedLocation) -> Presentation:
    prefs = visitor_preferences(session, visitor)
    return Presentation(
        units=schemas.Units(
            temperature=prefs.temperature_unit,  # type: ignore[arg-type]
            precipitation=prefs.precipitation_unit,  # type: ignore[arg-type]
            wind=prefs.wind_unit,  # type: ignore[arg-type]
        ),
        latitude=float(location.latitude),
        longitude=float(location.longitude),
        timezone=location.timezone,
    )


@router.get("/{location_id}/forecast", response_model=schemas.Forecast)
def get_forecast(
    location_id: UUID,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    hours: int = Query(default=72, ge=1, le=384),
    visitor: Visitor | None = Depends(optional_visitor),
    session: Session = Depends(get_db),
    provider: ForecastProvider = Depends(get_forecast_provider),
    now: datetime = Depends(get_now),
) -> schemas.Forecast | Response:
    location = get_location(session, _owner(visitor), location_id)
    assert visitor is not None
    presentation = _presentation(session, visitor, location)
    mark_grid_point_requested(session, location.grid_point)

    run = read_model.latest_run_for_point(
        session, location.weather_grid_point_id, provider.model_name
    )
    if run is None:
        response.headers["Cache-Control"] = "no-store"
        if not provider.available():
            return schemas.Forecast(
                status="unavailable",
                message="The forecast source is unavailable right now.",
                location=_location(location),
                units=presentation.units,
            )
        background.add_task(ensure_point_forecast, location.weather_grid_point_id, provider, now)
        return schemas.Forecast(
            status="processing",
            message="We're preparing the forecast for this location.",
            location=_location(location),
            units=presentation.units,
        )

    # Forecast data only changes when a run is ingested, but "now" moves the
    # current hour, so the validator includes the hour too.
    hour = now.replace(minute=0, second=0, microsecond=0)
    etag = (
        '"'
        + hashlib.sha256(
            f"{location.id}|{location.updated_at.isoformat()}|{run.id}|{presentation.units}|{hours}|{hour.isoformat()}".encode()
        ).hexdigest()[:32]
        + '"'
    )
    max_age = max(30, min(300, int((hour + timedelta(hours=1) - now).total_seconds())))
    cache_headers = {
        "ETag": etag,
        # private: the response is tied to the visitor cookie and their location.
        "Cache-Control": f"private, max-age={max_age}",
        "Vary": "Cookie",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)
    response.headers.update(cache_headers)

    forecast = read_model.load_grid_forecast(session, location.weather_grid_point_id, run)
    presenter = ForecastPresenter(presentation)
    today = now.astimezone(ZoneInfo(location.timezone)).date()
    return schemas.Forecast(
        status="ok",
        location=_location(location),
        units=presentation.units,
        model_run=model_run(run),
        current=presenter.current(forecast, now),
        hourly=[presenter.hourly(h) for h in select_hours(forecast, now, hours)],
        daily=[presenter.daily(d) for d in select_days(forecast, today)],
        rain_outlook=presenter.rain_outlook(forecast, now),
        summary=presenter.summary(forecast, now),
    )


@router.get("/{location_id}/forecast-history", response_model=schemas.ForecastHistory)
def get_forecast_history(
    location_id: UUID,
    target_time: datetime | None = Query(
        default=None,
        description="Target hour. Without an offset it is read in the location's timezone.",
    ),
    target_date: date | None = Query(
        default=None, description="Target local date (daily history)."
    ),
    metric: Literal["temperature", "precipitation", "wind"] = "temperature",
    visitor: Visitor | None = Depends(optional_visitor),
    session: Session = Depends(get_db),
    provider: ForecastProvider = Depends(get_forecast_provider),
    now: datetime = Depends(get_now),
) -> schemas.ForecastHistory:
    location = get_location(session, _owner(visitor), location_id)
    assert visitor is not None
    p = _presentation(session, visitor, location)
    tz = ZoneInfo(location.timezone)
    units = p.units
    gp_id = location.weather_grid_point_id

    today = now.astimezone(tz).date()
    available_dates = list(
        session.scalars(
            select(distinct(DailyForecast.local_date))
            .join(ForecastRun, ForecastRun.id == DailyForecast.forecast_run_id)
            .where(
                DailyForecast.weather_grid_point_id == gp_id,
                ForecastRun.model == provider.model_name,
                DailyForecast.local_date >= today - timedelta(days=7),
            )
            .order_by(DailyForecast.local_date)
        )
    )

    t = lambda c: convert_temperature(c, units.temperature)  # noqa: E731
    mm = lambda v: convert_precipitation(v, units.precipitation)  # noqa: E731
    w = lambda v: convert_wind(v, units.wind)  # noqa: E731

    entries: list[schemas.HistoryEntry] = []
    if target_time is not None:
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=tz)
        target_utc = target_time.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        for e in read_model.hourly_history(session, gp_id, provider.model_name, target_utc):
            h = e.hourly
            assert h is not None
            values = {
                "temperature": schemas.HistoryValue(
                    p10=t(h.temperature_p10_c),
                    p50=t(h.temperature_p50_c),
                    p90=t(h.temperature_p90_c),
                ),
                "precipitation": schemas.HistoryValue(
                    probability=h.precip_probability,
                    p50=mm(h.precip_p50_mm),
                    p90=mm(h.precip_p90_mm),
                ),
                "wind": schemas.HistoryValue(
                    p50=w(h.wind_speed_p50_mps), p90=w(h.wind_speed_p90_mps)
                ),
            }
            entries.append(
                schemas.HistoryEntry(
                    model_run=model_run(e.run),
                    lead_time_hours=e.lead_time_hours,
                    values={metric: values[metric]},
                )
            )
        target_time = target_utc.astimezone(tz)
    else:
        if target_date is None:
            if not available_dates:
                target_date = today
            else:
                future = [d for d in available_dates if d > today]
                target_date = future[min(3, len(future) - 1)] if future else available_dates[-1]
        for e in read_model.daily_history(session, gp_id, provider.model_name, target_date):
            d = e.daily
            assert d is not None
            if metric == "temperature":
                values = {
                    "high": schemas.HistoryValue(
                        p10=t(d.high_p10_c), p50=t(d.high_p50_c), p90=t(d.high_p90_c)
                    ),
                    "low": schemas.HistoryValue(
                        p10=t(d.low_p10_c), p50=t(d.low_p50_c), p90=t(d.low_p90_c)
                    ),
                }
            elif metric == "precipitation":
                values = {
                    "precipitation": schemas.HistoryValue(
                        probability=d.precip_probability,
                        p50=mm(d.precip_p50_mm),
                        p90=mm(d.precip_p90_mm),
                    )
                }
            else:
                values = {
                    "wind_max": schemas.HistoryValue(
                        p50=w(d.wind_max_p50_mps), p90=w(d.wind_max_p90_mps)
                    )
                }
            # Lead time to local noon of the target day, for display.
            noon = datetime.combine(target_date, datetime.min.time(), tz) + timedelta(hours=12)
            lead = int((noon - e.run.initialization_time).total_seconds() // 3600)
            entries.append(
                schemas.HistoryEntry(
                    model_run=model_run(e.run), lead_time_hours=lead, values=values
                )
            )

    if target_time is None and target_date is None:
        raise ApiError(422, "invalid_request", "Provide target_time or target_date")
    return schemas.ForecastHistory(
        location=_location(location),
        units=units,
        target_time=target_time,
        target_date=target_date if target_time is None else None,
        metric=metric,
        entries=entries,
        available_dates=available_dates,
    )

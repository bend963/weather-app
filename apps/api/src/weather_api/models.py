"""SQLAlchemy models.

Two families of tables live here and must stay separate:

* Ownership tables (visitors, users, saved_locations, visitor_preferences) hold
  what a person saved. They are private.
* Forecast tables (weather_grid_points, forecast_runs, hourly_forecasts,
  daily_forecasts) hold model output on a shared grid. They never reference an
  owner: one forecast for a grid cell serves every location inside that cell.

Forecast quantities use REAL (float4): more than enough precision for weather
values, half the storage of double precision on the largest tables, and no
Decimal conversion overhead. Coordinates use NUMERIC(9, 6) (~0.1 m).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    REAL,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


Coordinate = Numeric(9, 6)


# --- Ownership ---------------------------------------------------------------


class Visitor(Base):
    """An anonymous browser identity, referenced by the signed weather_visitor cookie."""

    __tablename__ = "visitors"

    id: Mapped[uuid.UUID] = _uuid_pk()
    created_at: Mapped[datetime] = _created_at()
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    preferences: Mapped["VisitorPreferences"] = relationship(
        back_populates="visitor", uselist=False, cascade="all, delete-orphan"
    )


class User(Base):
    """A registered account. Present for schema compatibility; no auth in v1."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = _created_at()


class VisitorPreferences(Base):
    __tablename__ = "visitor_preferences"

    visitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="CASCADE"), primary_key=True
    )
    temperature_unit: Mapped[str] = mapped_column(Text, nullable=False, server_default="F")
    precipitation_unit: Mapped[str] = mapped_column(Text, nullable=False, server_default="in")
    wind_unit: Mapped[str] = mapped_column(Text, nullable=False, server_default="mph")
    show_advanced_forecast: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    visitor: Mapped[Visitor] = relationship(back_populates="preferences")

    __table_args__ = (
        CheckConstraint("temperature_unit IN ('F', 'C')", name="ck_pref_temperature_unit"),
        CheckConstraint("precipitation_unit IN ('in', 'mm')", name="ck_pref_precip_unit"),
        CheckConstraint("wind_unit IN ('mph', 'kmh', 'mps', 'kt')", name="ck_pref_wind_unit"),
    )


class SavedLocation(Base):
    """A place someone saved. Owned by exactly one visitor or user.

    Signup will transfer ownership by setting visitor_id = NULL and user_id to
    the new account, which the owner check constraint keeps consistent.
    """

    __tablename__ = "saved_locations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    visitor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    weather_grid_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weather_grid_points.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Coordinate, nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Coordinate, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    elevation_m: Mapped[float | None] = mapped_column(REAL, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    grid_point: Mapped["WeatherGridPoint"] = relationship()

    __table_args__ = (
        CheckConstraint(
            "(visitor_id IS NULL) <> (user_id IS NULL)", name="ck_saved_locations_one_owner"
        ),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_saved_locations_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_saved_locations_longitude"),
        Index("ix_saved_locations_visitor", "visitor_id"),
        Index("ix_saved_locations_user", "user_id"),
        Index("ix_saved_locations_grid_point", "weather_grid_point_id"),
        # At most one default location per owner.
        Index(
            "uq_saved_locations_default_visitor",
            "visitor_id",
            unique=True,
            postgresql_where=text("is_default AND visitor_id IS NOT NULL"),
        ),
        Index(
            "uq_saved_locations_default_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default AND user_id IS NOT NULL"),
        ),
    )


# --- Shared forecast data ----------------------------------------------------


class WeatherGridPoint(Base):
    """One cell of the forecast model grid, shared by every location inside it."""

    __tablename__ = "weather_grid_points"

    id: Mapped[uuid.UUID] = _uuid_pk()
    latitude: Mapped[Decimal] = mapped_column(Coordinate, nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Coordinate, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_grid_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    # Used to group hourly values into local calendar days for daily_forecasts.
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    elevation_m: Mapped[float | None] = mapped_column(REAL, nullable=True)
    created_at: Mapped[datetime] = _created_at()
    last_requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("model_name", "model_grid_identifier", name="uq_grid_points_identifier"),
        Index("ix_grid_points_active", "active", postgresql_where=text("active")),
    )


RUN_STATUSES = ("pending", "processing", "complete", "failed")


class ForecastRun(Base):
    """One model initialization (e.g. the 00Z run). Never overwritten."""

    __tablename__ = "forecast_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    model: Mapped[str] = mapped_column(Text, nullable=False)
    initialization_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    forecast_horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        UniqueConstraint("model", "initialization_time", name="uq_forecast_runs_model_init"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'complete', 'failed')",
            name="ck_forecast_runs_status",
        ),
    )


class HourlyForecast(Base):
    """Ensemble statistics for one grid point, one model run, one valid hour."""

    __tablename__ = "hourly_forecasts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    weather_grid_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weather_grid_points.id"), nullable=False
    )
    forecast_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forecast_runs.id"), nullable=False
    )
    forecast_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lead_time_hours: Mapped[int] = mapped_column(Integer, nullable=False)

    temperature_p10_c: Mapped[float | None] = mapped_column(REAL)
    temperature_p50_c: Mapped[float] = mapped_column(REAL, nullable=False)
    temperature_p90_c: Mapped[float | None] = mapped_column(REAL)
    dewpoint_p50_c: Mapped[float | None] = mapped_column(REAL)
    wind_speed_p50_mps: Mapped[float | None] = mapped_column(REAL)
    wind_speed_p90_mps: Mapped[float | None] = mapped_column(REAL)
    wind_direction_deg: Mapped[float | None] = mapped_column(REAL)
    precip_probability: Mapped[float | None] = mapped_column(REAL)
    precip_p50_mm: Mapped[float | None] = mapped_column(REAL)
    precip_p90_mm: Mapped[float | None] = mapped_column(REAL)
    cloud_cover_p50: Mapped[float | None] = mapped_column(REAL)
    confidence_score: Mapped[float | None] = mapped_column(REAL)
    raw_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        UniqueConstraint(
            "weather_grid_point_id",
            "forecast_run_id",
            "forecast_time",
            name="uq_hourly_point_run_time",
        ),
        # Forecast history: every run's prediction for one target hour.
        Index("ix_hourly_point_time", "weather_grid_point_id", "forecast_time"),
    )


class DailyForecast(Base):
    """Precomputed per-local-day summary, derived from ensemble members."""

    __tablename__ = "daily_forecasts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    weather_grid_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weather_grid_points.id"), nullable=False
    )
    forecast_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forecast_runs.id"), nullable=False
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)

    high_p50_c: Mapped[float] = mapped_column(REAL, nullable=False)
    high_p10_c: Mapped[float | None] = mapped_column(REAL)
    high_p90_c: Mapped[float | None] = mapped_column(REAL)
    low_p50_c: Mapped[float] = mapped_column(REAL, nullable=False)
    low_p10_c: Mapped[float | None] = mapped_column(REAL)
    low_p90_c: Mapped[float | None] = mapped_column(REAL)
    precip_probability: Mapped[float | None] = mapped_column(REAL)
    precip_p50_mm: Mapped[float | None] = mapped_column(REAL)
    precip_p90_mm: Mapped[float | None] = mapped_column(REAL)
    wind_max_p50_mps: Mapped[float | None] = mapped_column(REAL)
    wind_max_p90_mps: Mapped[float | None] = mapped_column(REAL)
    confidence_score: Mapped[float | None] = mapped_column(REAL)
    # Separate agreement scores so the UI can say "temperature: high confidence,
    # rain: low confidence" for the same day.
    temperature_agreement: Mapped[float | None] = mapped_column(REAL)
    precip_agreement: Mapped[float | None] = mapped_column(REAL)
    raw_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        UniqueConstraint(
            "weather_grid_point_id", "forecast_run_id", "local_date", name="uq_daily_point_run_date"
        ),
        Index("ix_daily_point_date", "weather_grid_point_id", "local_date"),
    )

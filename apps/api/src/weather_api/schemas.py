"""API request/response models. Values are already converted to the caller's units."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from weather_api.units import PrecipitationUnit, TemperatureUnit, WindUnit

ConfidenceLevel = Literal["high", "medium", "low"]


class Units(BaseModel):
    temperature: TemperatureUnit
    precipitation: PrecipitationUnit
    wind: WindUnit


class Preferences(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    temperature_unit: TemperatureUnit
    precipitation_unit: PrecipitationUnit
    wind_unit: WindUnit
    show_advanced_forecast: bool


class PreferencesUpdate(BaseModel):
    temperature_unit: TemperatureUnit | None = None
    precipitation_unit: PrecipitationUnit | None = None
    wind_unit: WindUnit | None = None
    show_advanced_forecast: bool | None = None


class VisitorProfile(BaseModel):
    kind: Literal["anonymous"] = "anonymous"
    created_at: datetime


class Me(BaseModel):
    visitor: VisitorProfile
    preferences: Preferences
    location_count: int
    default_location_id: UUID | None


class Location(BaseModel):
    """A saved location. Exact coordinates are returned only to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    latitude: float
    longitude: float
    timezone: str
    is_default: bool
    created_at: datetime


def _clean_name(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("name must not be blank")
    return value


class LocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # rejects e.g. a smuggled visitor_id

    name: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    _name = field_validator("name")(_clean_name)


class LocationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    is_default: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)


class Place(BaseModel):
    name: str
    label: str
    latitude: float
    longitude: float
    country_code: str | None = None


class Range(BaseModel):
    p10: float | None
    p50: float | None
    p90: float | None


class Spread(BaseModel):
    p50: float | None
    p90: float | None


class Confidence(BaseModel):
    """Ensemble agreement. Not a calibrated probability of being correct."""

    score: float | None
    level: ConfidenceLevel | None


class Condition(BaseModel):
    code: str
    label: str


class ModelRun(BaseModel):
    id: UUID
    model: str
    initialization_time: datetime
    ingested_at: datetime
    forecast_horizon_hours: int
    status: str


class CurrentConditions(BaseModel):
    source: Literal["forecast", "observation"]
    time: datetime
    temperature: float | None
    feels_like: float | None
    dewpoint: float | None
    humidity: float | None
    wind_speed: float | None
    wind_direction_deg: float | None
    wind_direction: str | None
    cloud_cover: float | None
    precip_probability: float | None
    condition: Condition


class HourlyForecast(BaseModel):
    time: datetime
    lead_time_hours: int
    temperature: Range
    feels_like: float | None
    dewpoint: float | None
    wind_speed: Spread
    wind_direction_deg: float | None
    wind_direction: str | None
    precip_probability: float | None
    precip_amount: Spread
    precip_exceedance: dict[str, float] | None
    cloud_cover: float | None
    condition: Condition
    confidence: Confidence


class DayConfidence(BaseModel):
    overall: Confidence
    temperature: Confidence
    precipitation: Confidence
    temperature_summary: str
    precipitation_summary: str


class Distribution(BaseModel):
    edges: list[float]
    counts: list[int]


class DailyForecast(BaseModel):
    date: date
    high: Range
    low: Range
    precip_probability: float | None
    precip_amount: Spread
    precip_exceedance: dict[str, float] | None
    wind_max: Spread
    condition: Condition
    confidence: DayConfidence
    high_distribution: Distribution | None
    # Each ensemble member's high and low, in the same member order every day.
    # None for runs ingested before these were recorded.
    member_highs: list[float] | None = None
    member_lows: list[float] | None = None
    hours_covered: int | None
    members: int | None


class RainWindow(BaseModel):
    start: datetime
    end: datetime
    peak_probability: float
    expected_amount: float | None
    high_end_amount: float | None


class RainOutlook(BaseModel):
    next_rain: RainWindow | None
    summary: str
    horizon_hours: int


class Summary(BaseModel):
    next_24h_high: float | None
    next_24h_low: float | None
    next_24h_max_precip_probability: float | None
    next_24h_expected_precip: float | None
    members: int | None


ForecastStatus = Literal["ok", "processing", "unavailable"]


class Forecast(BaseModel):
    status: ForecastStatus
    message: str | None = None
    location: Location
    units: Units
    model_run: ModelRun | None = None
    current: CurrentConditions | None = None
    hourly: list[HourlyForecast] = []
    daily: list[DailyForecast] = []
    rain_outlook: RainOutlook | None = None
    summary: Summary | None = None


class HistoryValue(BaseModel):
    p10: float | None = None
    p50: float | None = None
    p90: float | None = None
    probability: float | None = None


class HistoryEntry(BaseModel):
    model_run: ModelRun
    lead_time_hours: int | None
    values: dict[str, HistoryValue]


class ForecastHistory(BaseModel):
    location: Location
    units: Units
    target_time: datetime | None = None
    target_date: date | None = None
    metric: Literal["temperature", "precipitation", "wind"]
    entries: list[HistoryEntry]
    available_dates: list[date]


class Health(BaseModel):
    status: Literal["ok"]

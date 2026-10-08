"""Shape SI forecast data into the API response, in the caller's units.

This is the only place units are converted and the only place forecast
uncertainty is put into words. The wording is deterministic and template
based, not generated.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from weather_api import schemas
from weather_api.forecast.conditions import (
    feels_like,
    is_daytime,
    relative_humidity,
    sky_condition,
)
from weather_api.forecast.confidence import level_for
from weather_api.forecast.current import CurrentConditionsProvider, NearestForecastHour
from weather_api.forecast.read_model import DailyPoint, GridForecast, HourlyPoint, RunInfo
from weather_api.units import (
    cardinal_direction,
    convert_precipitation,
    convert_temperature,
    convert_wind,
)

# Rain outlook: a window opens at the first hour at or above LIKELY and stays
# open while hours remain at or above CONTINUE.
RAIN_LIKELY_PROBABILITY = 0.4
RAIN_CONTINUE_PROBABILITY = 0.25
RAIN_OUTLOOK_HOURS = 7 * 24


@dataclass(frozen=True)
class Presentation:
    units: schemas.Units
    latitude: float
    longitude: float
    timezone: str


def model_run(run: RunInfo) -> schemas.ModelRun:
    return schemas.ModelRun(
        id=run.id,
        model=run.model,
        initialization_time=run.initialization_time,
        ingested_at=run.ingested_at,
        forecast_horizon_hours=run.forecast_horizon_hours,
        status=run.status,
    )


class ForecastPresenter:
    def __init__(
        self,
        p: Presentation,
        current_provider: CurrentConditionsProvider | None = None,
    ) -> None:
        self.p = p
        self.tz = ZoneInfo(p.timezone)
        self.current_provider = current_provider or NearestForecastHour()

    # --- unit helpers -------------------------------------------------------

    def t(self, c: float | None) -> float | None:
        return convert_temperature(c, self.p.units.temperature)

    def mm(self, v: float | None) -> float | None:
        return convert_precipitation(v, self.p.units.precipitation)

    def w(self, v: float | None) -> float | None:
        return convert_wind(v, self.p.units.wind)

    def local(self, dt: datetime) -> datetime:
        return dt.astimezone(self.tz)

    # --- sections ----------------------------------------------------------

    def hourly(self, h: HourlyPoint) -> schemas.HourlyForecast:
        return schemas.HourlyForecast(
            time=self.local(h.forecast_time),
            lead_time_hours=h.lead_time_hours,
            temperature=schemas.Range(
                p10=self.t(h.temperature_p10_c),
                p50=self.t(h.temperature_p50_c),
                p90=self.t(h.temperature_p90_c),
            ),
            feels_like=self.t(
                feels_like(h.temperature_p50_c, h.dewpoint_p50_c, h.wind_speed_p50_mps)
            ),
            dewpoint=self.t(h.dewpoint_p50_c),
            wind_speed=schemas.Spread(
                p50=self.w(h.wind_speed_p50_mps), p90=self.w(h.wind_speed_p90_mps)
            ),
            wind_direction_deg=h.wind_direction_deg,
            wind_direction=cardinal_direction(h.wind_direction_deg),
            precip_probability=h.precip_probability,
            precip_amount=schemas.Spread(
                p50=self.mm(h.precip_p50_mm), p90=self.mm(h.precip_p90_mm)
            ),
            precip_exceedance=h.raw_summary.get("precip_exceedance"),
            cloud_cover=h.cloud_cover_p50,
            condition=self._hour_condition(h),
            confidence=schemas.Confidence(
                score=_round(h.confidence_score), level=level_for(h.confidence_score)
            ),
        )

    def _hour_condition(self, h: HourlyPoint) -> schemas.Condition:
        c = sky_condition(
            cloud_cover=h.cloud_cover_p50,
            precip_probability=h.precip_probability,
            precip_amount_mm=h.raw_summary.get("precip_mean_mm", h.precip_p50_mm),
            temperature_c=h.temperature_p50_c,
            daytime=is_daytime(self.p.latitude, self.p.longitude, h.forecast_time),
        )
        return schemas.Condition(code=c.code, label=c.label)

    def daily(self, d: DailyPoint) -> schemas.DailyForecast:
        raw = d.raw_summary
        c = sky_condition(
            cloud_cover=raw.get("daytime_cloud_cover_p50"),
            precip_probability=d.precip_probability,
            precip_amount_mm=d.precip_p50_mm,
            temperature_c=d.high_p50_c,
            hours=24,
        )
        dist = raw.get("high_distribution_c")
        return schemas.DailyForecast(
            date=d.local_date,
            high=schemas.Range(
                p10=self.t(d.high_p10_c), p50=self.t(d.high_p50_c), p90=self.t(d.high_p90_c)
            ),
            low=schemas.Range(
                p10=self.t(d.low_p10_c), p50=self.t(d.low_p50_c), p90=self.t(d.low_p90_c)
            ),
            precip_probability=d.precip_probability,
            precip_amount=schemas.Spread(
                p50=self.mm(d.precip_p50_mm), p90=self.mm(d.precip_p90_mm)
            ),
            precip_exceedance=raw.get("precip_exceedance"),
            wind_max=schemas.Spread(p50=self.w(d.wind_max_p50_mps), p90=self.w(d.wind_max_p90_mps)),
            condition=schemas.Condition(code=c.code, label=c.label),
            confidence=self._day_confidence(d),
            high_distribution=(
                schemas.Distribution(
                    edges=[self.t(e) or 0.0 for e in dist["edges"]], counts=dist["counts"]
                )
                if dist
                else None
            ),
            hours_covered=raw.get("hours_covered"),
            members=raw.get("members"),
        )

    def _day_confidence(self, d: DailyPoint) -> schemas.DayConfidence:
        unit = f"°{self.p.units.temperature}"
        t_level = level_for(d.temperature_agreement)
        p_level = level_for(d.precip_agreement)
        lo, mid, hi = (_whole(self.t(x)) for x in (d.high_p10_c, d.high_p50_c, d.high_p90_c))

        if lo is None or hi is None or lo == hi:
            temp_text = f"High near {mid}{unit}"
        elif t_level == "high":
            temp_text = f"{lo}–{hi}{unit} likely"
        elif t_level == "medium":
            temp_text = f"Most likely {mid}{unit}, could be {lo}–{hi}{unit}"
        else:
            temp_text = f"Members disagree: highs anywhere from {lo} to {hi}{unit}"

        pop = d.precip_probability or 0.0
        if p_level == "high":
            rain_text = "Rain likely; members agree" if pop >= 0.5 else "Members agree it stays dry"
        elif p_level == "medium":
            rain_text = "Rain more likely than not" if pop >= 0.5 else "Some members show rain"
        else:
            rain_text = "Ensemble members disagree"

        return schemas.DayConfidence(
            overall=schemas.Confidence(
                score=_round(d.confidence_score), level=level_for(d.confidence_score)
            ),
            temperature=schemas.Confidence(score=_round(d.temperature_agreement), level=t_level),
            precipitation=schemas.Confidence(score=_round(d.precip_agreement), level=p_level),
            temperature_summary=temp_text,
            precipitation_summary=rain_text,
        )

    def current(self, forecast: GridForecast, now: datetime) -> schemas.CurrentConditions | None:
        cur = self.current_provider.current(forecast.hourly, now)
        if cur is None:
            return None
        nearest = min(
            forecast.hourly, key=lambda h: abs((h.forecast_time - cur.time).total_seconds())
        )
        humidity = (
            round(relative_humidity(cur.temperature_c, cur.dewpoint_c))
            if cur.dewpoint_c is not None
            else None
        )
        return schemas.CurrentConditions(
            source=cur.source,
            time=self.local(cur.time),
            temperature=self.t(cur.temperature_c),
            feels_like=self.t(feels_like(cur.temperature_c, cur.dewpoint_c, cur.wind_speed_mps)),
            dewpoint=self.t(cur.dewpoint_c),
            humidity=humidity,
            wind_speed=self.w(cur.wind_speed_mps),
            wind_direction_deg=cur.wind_direction_deg,
            wind_direction=cardinal_direction(cur.wind_direction_deg),
            cloud_cover=cur.cloud_cover,
            precip_probability=cur.precip_probability,
            condition=self._hour_condition(nearest),
        )

    def rain_outlook(self, forecast: GridForecast, now: datetime) -> schemas.RainOutlook:
        upcoming = [
            h
            for h in forecast.hourly
            if now - timedelta(hours=1)
            < h.forecast_time
            <= now + timedelta(hours=RAIN_OUTLOOK_HOURS)
        ]
        horizon = len(upcoming)
        days = max(1, round(horizon / 24))

        start_index = next(
            (
                i
                for i, h in enumerate(upcoming)
                if (h.precip_probability or 0) >= RAIN_LIKELY_PROBABILITY
            ),
            None,
        )
        if start_index is None:
            peak = max((h.precip_probability or 0 for h in upcoming), default=0.0)
            summary = (
                f"No rain likely in the next {days} days"
                if peak < 0.15
                else f"Low chance of rain in the next {days} days (at most {round(peak * 100)}%)"
            )
            return schemas.RainOutlook(next_rain=None, summary=summary, horizon_hours=horizon)

        end_index = start_index
        while (
            end_index + 1 < len(upcoming)
            and (upcoming[end_index + 1].precip_probability or 0) >= RAIN_CONTINUE_PROBABILITY
        ):
            end_index += 1
        window = upcoming[start_index : end_index + 1]
        peak = max(h.precip_probability or 0 for h in window)
        # Expected amount: the ensemble mean is additive across hours.
        expected = sum(h.raw_summary.get("precip_mean_mm", 0.0) for h in window)
        # High-end scenario: the wettest 10% of members' totals for the day(s)
        # the window falls on.
        window_dates = {self.local(h.forecast_time).date() for h in window}
        day_p90 = [d.precip_p90_mm or 0.0 for d in forecast.daily if d.local_date in window_dates]
        high_end = max([expected, *day_p90])

        # Each hourly value is the hour *ending* at forecast_time.
        start = self.local(window[0].forecast_time - timedelta(hours=1))
        end = self.local(window[-1].forecast_time)
        return schemas.RainOutlook(
            next_rain=schemas.RainWindow(
                start=start,
                end=end,
                peak_probability=round(peak, 2),
                expected_amount=self.mm(expected),
                high_end_amount=self.mm(high_end),
            ),
            summary=f"Rain likely {_describe_window(start, end, self.local(now))}",
            horizon_hours=horizon,
        )

    def summary(self, forecast: GridForecast, now: datetime) -> schemas.Summary:
        next_day = [
            h for h in forecast.hourly if now < h.forecast_time <= now + timedelta(hours=24)
        ]
        if not next_day:
            return schemas.Summary(
                next_24h_high=None,
                next_24h_low=None,
                next_24h_max_precip_probability=None,
                next_24h_expected_precip=None,
                members=None,
            )
        return schemas.Summary(
            next_24h_high=self.t(max(h.temperature_p50_c for h in next_day)),
            next_24h_low=self.t(min(h.temperature_p50_c for h in next_day)),
            next_24h_max_precip_probability=max(h.precip_probability or 0 for h in next_day),
            next_24h_expected_precip=self.mm(
                sum(h.raw_summary.get("precip_mean_mm", 0.0) for h in next_day)
            ),
            members=next_day[0].raw_summary.get("members"),
        )


def select_hours(forecast: GridForecast, now: datetime, hours: int) -> list[HourlyPoint]:
    """Hours from the current hour onward."""
    start = now.replace(minute=0, second=0, microsecond=0)
    return [h for h in forecast.hourly if h.forecast_time >= start][:hours]


def select_days(forecast: GridForecast, today: date) -> list[DailyPoint]:
    return [d for d in forecast.daily if d.local_date >= today]


def _describe_window(start: datetime, end: datetime, now: datetime) -> str:
    def day_name(dt: datetime) -> str:
        delta = (dt.date() - now.date()).days
        if delta == 0:
            return "today"
        if delta == 1:
            return "tomorrow"
        return dt.strftime("%A")

    def hour(dt: datetime) -> str:
        return dt.strftime("%I %p").lstrip("0")

    if start <= now:
        return f"now through {hour(end)}" + (
            "" if end.date() == now.date() else f" {day_name(end)}"
        )
    if start.date() == end.date():
        return f"{day_name(start)}, {hour(start)}–{hour(end)}"
    return f"{day_name(start)} {hour(start)} to {day_name(end)} {hour(end)}"


def _round(x: float | None) -> float | None:
    return None if x is None else round(x)


def _whole(x: float | None) -> int | None:
    return None if x is None else round(x)

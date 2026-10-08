"""Turn raw ensemble members into the statistics stored in the database.

All inputs and outputs are SI. Percentiles are taken across members at each
time step. Daily values are computed per member first (each member's own daily
high, low, total rain) and only then summarized across members: the median of
members' daily highs is a real "most likely high", whereas the max of hourly
medians would not be.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from weather_api.forecast.confidence import (
    combined_agreement,
    precip_agreement,
    temperature_agreement,
)
from weather_api.forecast.providers.base import EnsembleForecast

PERCENTILES = (10, 25, 50, 75, 90)

MM_PER_INCH = 25.4
# Below this an amount is a trace: too small to measure.
TRACE_MM = 0.1
# Exceedance thresholds reported for precipitation, in mm.
PRECIP_THRESHOLDS_MM: dict[str, float] = {
    "trace": TRACE_MM,
    "0.01in": 0.01 * MM_PER_INCH,
    "0.10in": 0.10 * MM_PER_INCH,
    "0.25in": 0.25 * MM_PER_INCH,
    "0.50in": 0.50 * MM_PER_INCH,
    "1.00in": 1.00 * MM_PER_INCH,
}
# "Chance of precipitation" follows the NWS PoP definition: at least 0.01 in.
POP_THRESHOLD_MM = PRECIP_THRESHOLDS_MM["0.01in"]

# A local day needs this many forecast hours to get a daily summary; the first
# and last days of a run are usually partial.
MIN_HOURS_FOR_DAILY = 12


def _r(x: float | np.floating | np.ndarray) -> float:
    return round(float(x), 3)


def exceedance_probabilities(amounts_mm: np.ndarray) -> dict[str, np.ndarray]:
    """Fraction of members above each threshold. amounts: (members, ...)."""
    return {k: (amounts_mm > v).mean(axis=0) for k, v in PRECIP_THRESHOLDS_MM.items()}


def wind_speed_and_direction(u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-member speed, plus the direction of the ensemble-mean wind vector.

    Direction is averaged as a vector: averaging angles directly would make
    350° and 10° average to 180°.
    """
    speed = np.hypot(u, v)
    mean_u, mean_v = u.mean(axis=0), v.mean(axis=0)
    direction = (np.degrees(np.arctan2(-mean_u, -mean_v)) + 360.0) % 360.0
    return speed, direction


@dataclass
class HourlyStats:
    forecast_time: datetime
    lead_time_hours: int
    temperature_p10_c: float
    temperature_p50_c: float
    temperature_p90_c: float
    dewpoint_p50_c: float
    wind_speed_p50_mps: float
    wind_speed_p90_mps: float
    wind_direction_deg: float
    precip_probability: float
    precip_p50_mm: float
    precip_p90_mm: float
    cloud_cover_p50: float
    confidence_score: float
    raw_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class DailyStats:
    local_date: date
    high_p10_c: float
    high_p50_c: float
    high_p90_c: float
    low_p10_c: float
    low_p50_c: float
    low_p90_c: float
    precip_probability: float
    precip_p50_mm: float
    precip_p90_mm: float
    wind_max_p50_mps: float
    wind_max_p90_mps: float
    temperature_agreement: float
    precip_agreement: float
    confidence_score: float
    raw_summary: dict[str, Any] = field(default_factory=dict)


def hourly_statistics(fc: EnsembleForecast) -> list[HourlyStats]:
    t_pct = np.percentile(fc.temperature_c, PERCENTILES, axis=0)
    dew_p50 = np.median(fc.dewpoint_c, axis=0)
    speed, direction = wind_speed_and_direction(fc.wind_u_mps, fc.wind_v_mps)
    w_pct = np.percentile(speed, PERCENTILES, axis=0)
    p_pct = np.percentile(fc.precip_mm, PERCENTILES, axis=0)
    p_mean = fc.precip_mm.mean(axis=0)
    cloud_p50 = np.median(fc.cloud_cover, axis=0)
    exceed = exceedance_probabilities(fc.precip_mm)
    pop = (fc.precip_mm > POP_THRESHOLD_MM).mean(axis=0)

    t_agree = temperature_agreement(t_pct[0], t_pct[4])
    p_agree = precip_agreement(pop)
    overall = combined_agreement(t_agree, p_agree)

    rows: list[HourlyStats] = []
    for i, valid_time in enumerate(fc.valid_times):
        rows.append(
            HourlyStats(
                forecast_time=valid_time,
                lead_time_hours=int(fc.lead_time_hours[i]),
                temperature_p10_c=_r(t_pct[0, i]),
                temperature_p50_c=_r(t_pct[2, i]),
                temperature_p90_c=_r(t_pct[4, i]),
                dewpoint_p50_c=_r(dew_p50[i]),
                wind_speed_p50_mps=_r(w_pct[2, i]),
                wind_speed_p90_mps=_r(w_pct[4, i]),
                wind_direction_deg=_r(direction[i]),
                precip_probability=_r(pop[i]),
                precip_p50_mm=_r(p_pct[2, i]),
                precip_p90_mm=_r(p_pct[4, i]),
                cloud_cover_p50=_r(cloud_p50[i]),
                confidence_score=_r(overall[i]),
                raw_summary={
                    "members": fc.member_count,
                    "temperature_p25_c": _r(t_pct[1, i]),
                    "temperature_p75_c": _r(t_pct[3, i]),
                    "wind_speed_p10_mps": _r(w_pct[0, i]),
                    "precip_p75_mm": _r(p_pct[3, i]),
                    # The mean is additive across hours, unlike percentiles,
                    # so it is what multi-hour "expected rain" sums use.
                    "precip_mean_mm": _r(p_mean[i]),
                    "precip_exceedance": {k: _r(v[i]) for k, v in exceed.items()},
                    "temperature_agreement": _r(t_agree[i]),
                    "precip_agreement": _r(p_agree[i]),
                },
            )
        )
    return rows


def daily_statistics(fc: EnsembleForecast, timezone: str) -> list[DailyStats]:
    tz = ZoneInfo(timezone)
    local_dates = np.array([t.astimezone(tz).date() for t in fc.valid_times])
    local_hours = np.array([t.astimezone(tz).hour for t in fc.valid_times])
    speed, _ = wind_speed_and_direction(fc.wind_u_mps, fc.wind_v_mps)

    rows: list[DailyStats] = []
    for day in sorted(set(local_dates)):
        mask = local_dates == day
        hours = int(mask.sum())
        if hours < MIN_HOURS_FOR_DAILY:
            continue

        # Each member's own daily extremes and totals, then percentiles across members.
        highs = fc.temperature_c[:, mask].max(axis=1)
        lows = fc.temperature_c[:, mask].min(axis=1)
        totals = fc.precip_mm[:, mask].sum(axis=1)
        wind_max = speed[:, mask].max(axis=1)
        h = np.percentile(highs, PERCENTILES)
        lo = np.percentile(lows, PERCENTILES)
        p = np.percentile(totals, PERCENTILES)
        w = np.percentile(wind_max, PERCENTILES)
        pop = float((totals > POP_THRESHOLD_MM).mean())

        daytime = mask & (local_hours >= 8) & (local_hours <= 18)
        cloud_mask = daytime if daytime.any() else mask
        daytime_cloud = float(np.median(fc.cloud_cover[:, cloud_mask]))

        # Agreement on the high is the most user-relevant temperature signal.
        t_agree = float(temperature_agreement(h[0], h[4]))
        p_agree = float(precip_agreement(pop))
        rows.append(
            DailyStats(
                local_date=day,
                high_p10_c=_r(h[0]),
                high_p50_c=_r(h[2]),
                high_p90_c=_r(h[4]),
                low_p10_c=_r(lo[0]),
                low_p50_c=_r(lo[2]),
                low_p90_c=_r(lo[4]),
                precip_probability=_r(pop),
                precip_p50_mm=_r(p[2]),
                precip_p90_mm=_r(p[4]),
                wind_max_p50_mps=_r(w[2]),
                wind_max_p90_mps=_r(w[4]),
                temperature_agreement=_r(t_agree),
                precip_agreement=_r(p_agree),
                confidence_score=_r(float(combined_agreement(t_agree, p_agree))),
                raw_summary={
                    "members": fc.member_count,
                    "hours_covered": hours,
                    "high_p25_c": _r(h[1]),
                    "high_p75_c": _r(h[3]),
                    "low_p25_c": _r(lo[1]),
                    "low_p75_c": _r(lo[3]),
                    "precip_p25_mm": _r(p[1]),
                    "precip_p75_mm": _r(p[3]),
                    "precip_mean_mm": _r(totals.mean()),
                    "precip_exceedance": {
                        k: _r(v) for k, v in exceedance_probabilities(totals).items()
                    },
                    "daytime_cloud_cover_p50": _r(daytime_cloud),
                    # A coarse histogram of members' highs for the advanced drawer.
                    "high_distribution_c": _histogram(highs),
                },
            )
        )
    return rows


def _histogram(values: np.ndarray, bins: int = 8) -> dict[str, list[float]]:
    counts, edges = np.histogram(values, bins=bins)
    return {"edges": [_r(e) for e in edges], "counts": [int(c) for c in counts]}

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from weather_api.forecast.confidence import level_for, precip_agreement, temperature_agreement
from weather_api.forecast.ensemble import (
    MM_PER_INCH,
    daily_statistics,
    exceedance_probabilities,
    hourly_statistics,
    wind_speed_and_direction,
)
from weather_api.forecast.providers.base import EnsembleForecast


def make_forecast(
    temperature: np.ndarray, precip: np.ndarray | None = None, start=None
) -> EnsembleForecast:
    members, hours = temperature.shape
    start = start or datetime(2026, 10, 8, 4, tzinfo=UTC)  # local midnight in New York
    zeros = np.zeros_like(temperature)
    return EnsembleForecast(
        valid_times=[start + timedelta(hours=h) for h in range(hours)],
        lead_time_hours=np.arange(hours),
        temperature_c=temperature,
        dewpoint_c=temperature - 5,
        wind_u_mps=zeros + 3,
        wind_v_mps=zeros,
        precip_mm=zeros if precip is None else precip,
        cloud_cover=zeros + 0.5,
    )


def test_hourly_percentiles_across_members():
    # Members 0..10 °C at every hour.
    temps = np.tile(np.arange(11, dtype=float)[:, None], (1, 3))
    rows = hourly_statistics(make_forecast(temps))
    assert len(rows) == 3
    assert rows[0].temperature_p10_c == pytest.approx(1)
    assert rows[0].temperature_p50_c == pytest.approx(5)
    assert rows[0].temperature_p90_c == pytest.approx(9)
    assert rows[0].raw_summary["temperature_p25_c"] == pytest.approx(2.5)


def test_precipitation_exceedance_thresholds():
    amounts = np.array([0, 0.2, 0.3, 3.0, 7.0, 13.0, 30.0, 0, 0, 0], dtype=float)
    p = exceedance_probabilities(amounts)
    assert p["trace"] == pytest.approx(0.6)
    assert p["0.01in"] == pytest.approx(0.5)
    assert p["0.10in"] == pytest.approx(0.4)
    assert p["0.25in"] == pytest.approx(0.3)
    assert p["0.50in"] == pytest.approx(0.2)
    assert p["1.00in"] == pytest.approx(0.1)
    assert 1.0 * MM_PER_INCH == 25.4


def test_wind_direction_is_a_vector_mean():
    # From 350° and from 10°: the mean is from the north, not from the south.
    def uv(deg, speed=5):
        r = np.deg2rad(deg)
        return -speed * np.sin(r), -speed * np.cos(r)

    u1, v1 = uv(350)
    u2, v2 = uv(10)
    speed, direction = wind_speed_and_direction(np.array([[u1], [u2]]), np.array([[v1], [v2]]))
    assert speed[:, 0] == pytest.approx([5, 5])
    assert direction[0] == pytest.approx(0, abs=1e-6) or direction[0] == pytest.approx(
        360, abs=1e-6
    )
    _, west = wind_speed_and_direction(np.array([[5.0]]), np.array([[0.0]]))
    assert west[0] == pytest.approx(270)


def test_daily_values_are_computed_per_member_then_summarized():
    hours = 48
    temps = np.zeros((2, hours))
    # Member 0 peaks at 30 °C in the morning; member 1 peaks at 30 °C in the
    # evening. Hourly medians never exceed 15 °C, but both members' highs are 30.
    temps[0, 9] = 30
    temps[1, 20] = 30
    precip = np.zeros((2, hours))
    precip[0, 2:6] = 2.0  # member 0: 8 mm on day one
    rows = daily_statistics(make_forecast(temps, precip), "America/New_York")
    assert [r.local_date.isoformat() for r in rows] == ["2026-10-08", "2026-10-09"]
    day1 = rows[0]
    assert day1.high_p50_c == pytest.approx(30)
    assert day1.low_p50_c == pytest.approx(0)
    assert day1.precip_probability == pytest.approx(0.5)
    assert day1.precip_p90_mm == pytest.approx(7.2)
    assert day1.raw_summary["hours_covered"] == 24
    assert sum(day1.raw_summary["high_distribution_c"]["counts"]) == 2


def test_daily_grouping_uses_the_local_timezone():
    temps = np.zeros((1, 24))
    # 04:00 UTC start is local midnight in New York but 13:00 in Tokyo.
    tokyo = daily_statistics(make_forecast(temps), "Asia/Tokyo")
    ny = daily_statistics(make_forecast(temps), "America/New_York")
    assert len(ny) == 1 and ny[0].raw_summary["hours_covered"] == 24
    # Tokyo: 11 hours on Oct 8 (dropped, < 12) and 13 on Oct 9.
    assert [r.local_date.isoformat() for r in tokyo] == ["2026-10-09"]


def test_confidence_from_spread():
    assert level_for(float(temperature_agreement(20, 21.5))) == "high"
    assert level_for(float(temperature_agreement(20, 25))) == "medium"
    assert level_for(float(temperature_agreement(20, 28))) == "low"
    assert level_for(float(precip_agreement(0.02))) == "high"
    assert level_for(float(precip_agreement(0.5))) == "low"
    assert level_for(float(precip_agreement(0.95))) == "high"
    assert level_for(None) is None

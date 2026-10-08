import uuid
from datetime import UTC, datetime

import numpy as np
from weather_api.forecast.providers import GridPointRef, MockForecastProvider

GP = GridPointRef(uuid.uuid4(), "114:1115", 28.5, -81.25, "America/New_York")


def test_initializations_follow_a_12_hour_cycle_with_latency():
    p = MockForecastProvider()
    inits = p.latest_initializations(3, now=datetime(2026, 10, 8, 15, 30, tzinfo=UTC))
    assert inits == [
        datetime(2026, 10, 8, 0, tzinfo=UTC),
        datetime(2026, 10, 7, 12, tzinfo=UTC),
        datetime(2026, 10, 7, 0, tzinfo=UTC),
    ]
    # 12Z isn't available until 17Z.
    assert p.latest_initializations(1, now=datetime(2026, 10, 8, 17, 1, tzinfo=UTC))[0].hour == 12


def test_forecasts_are_deterministic():
    p = MockForecastProvider(members=10, horizon_hours=48)
    init = datetime(2026, 10, 8, tzinfo=UTC)
    a = p.get_forecast([GP], init)[GP.id]
    b = MockForecastProvider(members=10, horizon_hours=48).get_forecast([GP], init)[GP.id]
    np.testing.assert_array_equal(a.temperature_c, b.temperature_c)
    np.testing.assert_array_equal(a.precip_mm, b.precip_mm)


def test_runs_differ_but_share_underlying_weather():
    p = MockForecastProvider(members=30, horizon_hours=120)
    a = p.get_forecast([GP], datetime(2026, 10, 8, tzinfo=UTC))[GP.id]
    b = p.get_forecast([GP], datetime(2026, 10, 8, 12, tzinfo=UTC))[GP.id]
    # Same valid time (a's hour 24 == b's hour 12): different, but close.
    ta = np.median(a.temperature_c[:, 24])
    tb = np.median(b.temperature_c[:, 12])
    assert ta != tb
    assert abs(ta - tb) < 4


def test_spread_grows_with_lead_time_and_values_are_plausible():
    fc = MockForecastProvider(members=50, horizon_hours=240).get_forecast(
        [GP], datetime(2026, 10, 8, tzinfo=UTC)
    )[GP.id]
    spread = np.percentile(fc.temperature_c, 90, axis=0) - np.percentile(
        fc.temperature_c, 10, axis=0
    )
    assert spread[200:].mean() > 2 * spread[:24].mean()
    assert fc.temperature_c.shape == (50, 241)
    assert fc.temperature_c.min() > -10 and fc.temperature_c.max() < 45
    assert (fc.dewpoint_c <= fc.temperature_c).all()
    assert (fc.precip_mm >= 0).all()
    assert ((fc.cloud_cover >= 0) & (fc.cloud_cover <= 1)).all()
    assert (fc.precip_mm > 0.254).any()  # it rains at some point in ten days

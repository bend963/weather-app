from datetime import UTC, datetime

import pytest
from weather_api.forecast.conditions import feels_like, is_daytime, relative_humidity, sky_condition


def f_to_c(f: float) -> float:
    return (f - 32) * 5 / 9


def test_heat_index_matches_nws_table():
    # NWS table: 90 °F at 60% RH -> ~100 °F.
    t = f_to_c(90)
    dew = f_to_c(74.6)  # ~60% RH at 90 °F
    assert relative_humidity(t, dew) == pytest.approx(60, abs=1.5)
    assert feels_like(t, dew, 2) * 9 / 5 + 32 == pytest.approx(100, abs=2)


def test_wind_chill_matches_nws_table():
    # NWS table: 20 °F with 15 mph wind -> 6 °F.
    assert feels_like(f_to_c(20), None, 15 / 2.236936) * 9 / 5 + 32 == pytest.approx(6, abs=1)


def test_mild_conditions_feel_like_air_temperature():
    assert feels_like(18.0, 10.0, 5.0) == 18.0


def test_daytime():
    # Orlando: 18:00 UTC is early afternoon, 06:00 UTC is the middle of the night.
    assert is_daytime(28.5, -81.3, datetime(2026, 10, 8, 18, tzinfo=UTC))
    assert not is_daytime(28.5, -81.3, datetime(2026, 10, 8, 6, tzinfo=UTC))


def test_sky_condition_buckets():
    clear = sky_condition(
        cloud_cover=0.05, precip_probability=0, precip_amount_mm=0, temperature_c=20
    )
    assert clear.code == "clear-day"
    night = sky_condition(
        cloud_cover=0.05, precip_probability=0, precip_amount_mm=0, temperature_c=20, daytime=False
    )
    assert night.label == "Clear"
    assert (
        sky_condition(
            cloud_cover=0.8, precip_probability=0.1, precip_amount_mm=0, temperature_c=20
        ).label
        == "Mostly cloudy"
    )
    assert (
        sky_condition(
            cloud_cover=0.9, precip_probability=0.8, precip_amount_mm=1.2, temperature_c=20
        ).code
        == "rain"
    )
    assert (
        sky_condition(
            cloud_cover=0.9, precip_probability=0.8, precip_amount_mm=1.2, temperature_c=-2
        ).code
        == "snow"
    )
    assert (
        sky_condition(
            cloud_cover=0.5, precip_probability=0.35, precip_amount_mm=0, temperature_c=20
        ).code
        == "chance-rain"
    )

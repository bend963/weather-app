import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from weather_api.forecast.ensemble import daily_statistics, hourly_statistics
from weather_api.forecast.providers import GridPointRef, ProviderUnavailable
from weather_api.forecast.providers.weathernext import (
    COLUMNS,
    TABLE,
    WeatherNextProvider,
    forecast_sql,
)
from weather_api.forecast.spread_paths import (
    PATH_COUNT,
    precipitation_paths,
    spread_paths,
    wind_paths,
)

INIT = datetime(2026, 10, 19, 6, tzinfo=UTC)
GP = GridPointRef(uuid.uuid4(), "285:2787", 28.5, -81.3, "America/New_York")


def test_spread_paths_reproduce_the_published_percentiles():
    q = np.array([[10.0, 0.0], [12.0, 1.0], [15.0, 2.0], [16.0, 5.0], [20.0, 9.0]])
    paths = spread_paths(q)
    assert paths.shape == (PATH_COUNT, 2)
    assert np.allclose(np.percentile(paths, (10, 25, 50, 75, 90), axis=0), q)
    assert (np.diff(paths, axis=0) >= 0).all()  # path k sits at the same level every hour
    # Tails continue the outer slopes: 2 per 0.15 below p10, 4 per 0.15 above p90.
    assert paths[0, 0] == pytest.approx(10.0 - 2.0 * 0.10 / 0.15)
    assert paths[-1, 0] == pytest.approx(20.0 + 4.0 * 0.10 / 0.15)


def test_spread_paths_clip_to_physical_limits():
    cloud = spread_paths(np.array([[0.0], [0.1], [0.5], [0.95], [1.0]]), lower=0.0, upper=1.0)
    assert cloud.min() == 0.0 and cloud.max() == 1.0


def test_precipitation_paths_keep_the_mean_and_the_percentiles():
    q = np.array([[0.0], [0.0], [0.0], [0.4], [2.0]])
    paths = precipitation_paths(q, mean=np.array([0.9]))
    assert paths.mean() == pytest.approx(0.9)
    assert np.allclose(np.percentile(paths, (10, 25, 50, 75, 90), axis=0), q)
    assert paths.min() >= 0.0
    # Chance of at least 0.01 in (0.254 mm) lands between the 50th and 75th percentile.
    assert 0.25 < (paths > 0.254).mean() < 0.5


def test_wind_paths_follow_speed_percentiles_and_mean_direction():
    speed_q = np.array([[2.0], [3.0], [4.0], [5.0], [7.0]])
    u, v = wind_paths(speed_q, mean_u=np.array([3.0]), mean_v=np.array([-3.0]))
    assert np.allclose(np.percentile(np.hypot(u, v), (10, 25, 50, 75, 90), axis=0), speed_q)
    assert np.allclose(u, -v)  # all along the mean wind's heading (from the northwest)
    calm_u, calm_v = wind_paths(speed_q, mean_u=np.array([0.0]), mean_v=np.array([0.0]))
    assert np.allclose(np.hypot(calm_u, calm_v), np.hypot(u, v))


def _rows(node_id: str, hours: int = 48) -> list[dict]:
    """Rows shaped like the forecast query's output, in the table's units."""
    rows = []
    for h in range(1, hours + 1):
        row = {"id": node_id, "time": INIT + timedelta(hours=h), "hours": h}
        diurnal = 4.0 * np.sin((h - 9) / 24 * 2 * np.pi)
        spread = 0.5 + h / 48
        for c in COLUMNS:
            name, stat = c.rsplit("_", 1)
            z = {"p10": -1.28, "p25": -0.67, "p50": 0.0, "p75": 0.67, "p90": 1.28, "mean": 0.0}[
                stat
            ]
            if name == "temperature_2m":
                row[c] = 273.15 + 25 + diurnal + z * spread
            elif name == "dewpoint_temperature_2m":
                row[c] = 273.15 + 18 + z * spread
            elif name == "wind_speed_10m":
                row[c] = max(0.0, 4.0 + z)
            elif name == "u_component_of_wind_10m":
                row[c] = 2.0
            elif name == "v_component_of_wind_10m":
                row[c] = 1.0
            elif name == "total_precipitation_1hr":
                wet = 20 <= h <= 23
                mm = {"p10": 0, "p25": 0, "p50": 0, "p75": 0.5, "p90": 3.0, "mean": 1.2}[stat]
                row[c] = (mm if wet else 0.0) / 1000.0
            else:  # total_cloud_cover
                row[c] = min(1.0, max(0.0, 0.5 + 0.3 * z))
        rows.append(row)
    return rows


class FakeJob:
    def __init__(self, rows):
        self.rows = rows
        self.total_bytes_billed = 12345

    def result(self):
        return iter(self.rows)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[tuple[str, object]] = []

    def query(self, sql, job_config=None):
        self.calls.append((sql, job_config))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return FakeJob(result)


def _provider(*responses) -> tuple[WeatherNextProvider, FakeClient]:
    client = FakeClient(responses)
    provider = WeatherNextProvider(
        project="ben-weather", dataset="weathernext", client=client, max_bytes_billed=10**12
    )
    return provider, client


def test_get_forecast_turns_rows_into_spread_paths_in_si_units():
    provider, client = _provider(_rows(str(GP.id)))
    fc = provider.get_forecast([GP], INIT)[GP.id]

    assert fc.from_percentiles and fc.ensemble_size == 64
    assert fc.member_count == PATH_COUNT
    assert fc.valid_times[0] == INIT + timedelta(hours=1)
    assert list(fc.lead_time_hours[:3]) == [1, 2, 3]
    # Kelvin -> °C, metres -> mm.
    assert np.median(fc.temperature_c[:, 8]) == pytest.approx(25.0, abs=0.01)
    assert np.median(fc.dewpoint_c[:, 0]) == pytest.approx(18.0, abs=0.01)
    assert fc.precip_mm[:, 20].mean() == pytest.approx(1.2)
    assert fc.precip_mm[:, 5].max() == 0.0

    sql, config = client.calls[0]
    assert f"`ben-weather.weathernext.{TABLE}`" in sql
    assert "t.init_time = @init_time" in sql
    assert config.maximum_bytes_billed == 10**12
    params = {p.name: p.value for p in config.query_parameters}
    assert params["init_time"] == INIT
    assert (params["lat0"], params["lon0"], params["id0"]) == (28.5, -81.3, str(GP.id))


def test_spread_path_forecasts_feed_the_normal_statistics():
    provider, _ = _provider(_rows(str(GP.id), hours=72))
    fc = provider.get_forecast([GP], INIT)[GP.id]

    hourly = hourly_statistics(fc)
    assert hourly[8].temperature_p50_c == pytest.approx(25.0, abs=0.01)
    assert hourly[8].temperature_p90_c == pytest.approx(25.0 + 1.28 * (0.5 + 9 / 48), abs=0.01)
    assert hourly[8].raw_summary["members"] == 64
    assert hourly[8].raw_summary["from_percentiles"] is True
    assert 0.25 < hourly[20].precip_probability < 0.5
    assert hourly[5].precip_probability == 0.0

    days = daily_statistics(fc, GP.timezone)
    assert days and days[0].raw_summary["from_percentiles"] is True
    assert len(days[0].raw_summary["member_highs_c"]) == PATH_COUNT


def test_dataset_may_name_its_own_project():
    provider = WeatherNextProvider(project="billing", dataset="shared-proj.wn3")
    assert provider.table == f"shared-proj.wn3.{TABLE}"


def test_points_without_rows_are_left_out():
    other = GridPointRef(uuid.uuid4(), "0:0", 0.0, 0.0, "UTC")
    provider, _ = _provider(_rows(str(GP.id), hours=3))
    assert set(provider.get_forecast([GP, other], INIT)) == {GP.id}


def test_cells_with_missing_values_are_skipped():
    rows = _rows(str(GP.id), hours=3)
    rows[1]["temperature_2m_p50"] = None
    provider, _ = _provider(rows)
    assert provider.get_forecast([GP], INIT) == {}


def test_latest_initializations_returns_published_main_runs_newest_first():
    published = [INIT - timedelta(hours=6), INIT]
    provider, client = _provider([{"init_time": t} for t in published])
    now = INIT + timedelta(hours=9)
    assert provider.latest_initializations(2, now=now) == [INIT, INIT - timedelta(hours=6)]

    candidates = next(p for p in client.calls[0][1].query_parameters if p.name == "candidates")
    assert candidates.values[0] == INIT  # 06Z is the newest run Google could have published by 15Z
    assert all(t.hour % 6 == 0 for t in candidates.values)


def test_latest_initializations_skips_runs_not_yet_published():
    provider, client = _provider([])
    with pytest.raises(ProviderUnavailable):
        provider.latest_initializations(1, now=INIT + timedelta(hours=8))
    candidates = next(p for p in client.calls[0][1].query_parameters if p.name == "candidates")
    assert candidates.values[0] == INIT - timedelta(hours=6)


def test_query_errors_become_provider_unavailable():
    provider, _ = _provider(RuntimeError("403 Access Denied"))
    with pytest.raises(ProviderUnavailable, match="Access Denied"):
        provider.get_forecast([GP], INIT)


def test_unconfigured_provider_is_unavailable():
    provider = WeatherNextProvider(project=None, dataset=None)
    assert not provider.available()
    with pytest.raises(ProviderUnavailable):
        provider.latest_initializations(1)


def test_forecast_sql_filters_every_node_and_reads_only_needed_columns():
    sql = forecast_sql(f"p.d.{TABLE}", 3)
    assert sql.count("ST_DWITHIN(t.geography, ST_GEOGPOINT(@lon") == 3
    assert "@id2" in sql and "@id3" not in sql
    assert "SELECT *\nFROM" not in sql
    for c in COLUMNS:
        assert f"f.{c}" in sql

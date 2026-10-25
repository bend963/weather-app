import uuid
from datetime import UTC, datetime

import httpx
import numpy as np
import pytest
from weather_api.forecast.providers import GridPointRef, ProviderUnavailable
from weather_api.forecast.providers.gefs import (
    GefsProvider,
    StepValues,
    bilinear_weights,
    parse_idx,
    to_hourly,
)

IDX = """\
1:0:d=2026100906:HGT:10 mb:6 hour fcst:ENS=+1
2:1000:d=2026100906:TMP:2 m above ground:6 hour fcst:ENS=+1
3:2500:d=2026100906:RH:2 m above ground:6 hour fcst:ENS=+1
4:4000:d=2026100906:UGRD:10 m above ground:6 hour fcst:ENS=+1
5:5200:d=2026100906:VGRD:10 m above ground:6 hour fcst:ENS=+1
6:6400:d=2026100906:APCP:surface:0-6 hour acc fcst:ENS=+1
7:7000:d=2026100906:CAPE:surface:6 hour fcst:ENS=+1
8:8100:d=2026100906:TCDC:entire atmosphere:0-6 hour ave fcst:ENS=+1
"""


def test_parse_idx_keeps_wanted_fields_with_byte_ranges():
    fields = {f.name: f for f in parse_idx(IDX)}
    assert set(fields) == {"t", "rh", "u", "v", "tp", "tcc"}
    assert (fields["t"].start, fields["t"].end, fields["t"].bucket) == (1000, 2499, None)
    assert (fields["tp"].start, fields["tp"].end, fields["tp"].bucket) == (6400, 6999, (0, 6))
    # The file's last message runs to the end of the file.
    assert (fields["tcc"].end, fields["tcc"].bucket) == (None, (0, 6))


def test_bilinear_weights_on_and_between_grid_nodes():
    on = [(i, j, w) for i, j, w in bilinear_weights(28.5, -81.5) if w > 0]
    assert on == [(123, 557, 1.0)]  # 90 - 28.5 = 61.5° -> row 123; -81.5 = 278.5° -> column 557

    between = bilinear_weights(28.25, 278.75)
    assert {(i, j) for i, j, _ in between} == {(123, 557), (124, 557), (123, 558), (124, 558)}
    assert all(w == pytest.approx(0.25) for _, _, w in between)


def test_bilinear_weights_wrap_at_the_dateline_and_stay_on_the_grid_at_the_pole():
    cols = {j for _, j, _ in bilinear_weights(0.0, 359.75)}
    assert cols == {719, 0}
    rows = {i for i, _, w in bilinear_weights(-90.0, 0.0) if w > 0}
    assert rows == {360}


def _step(t_k, rh, bucket=None, tp=0.0, tcc=0.0):
    instant = {
        "t": np.array([t_k]),
        "rh": np.array([rh]),
        "u": np.array([1.0]),
        "v": np.array([-2.0]),
    }
    buckets = (
        {} if bucket is None else {"tp": (bucket, np.array([tp])), "tcc": (bucket, np.array([tcc]))}
    )
    return StepValues(instant=instant, buckets=buckets)


def test_to_hourly_interpolates_and_unwinds_6_hour_buckets():
    steps = [0, 3, 6, 9, 12]
    values = [
        _step(283.15, 100),
        _step(286.15, 100, (0, 3), tp=3.0, tcc=50),
        _step(289.15, 100, (0, 6), tp=9.0, tcc=75),  # 6 mm more in hours 4–6; cloud 100% then
        _step(289.15, 100, (6, 9), tp=1.0, tcc=0),
        _step(289.15, 100, (6, 12), tp=1.0, tcc=0),  # nothing after hour 9
    ]
    h = to_hourly(steps, values, horizon=12)
    assert h["t"].shape == (1, 13)
    np.testing.assert_allclose(h["t"][0, [0, 1, 3, 6]], [10.0, 11.0, 13.0, 16.0])
    # Saturated air: dewpoint equals temperature.
    np.testing.assert_allclose(h["td"], h["t"], atol=1e-9)
    np.testing.assert_allclose(h["v"], -2.0)
    expected_p = [0, 1, 1, 1, 2, 2, 2, 1 / 3, 1 / 3, 1 / 3, 0, 0, 0]
    np.testing.assert_allclose(h["p"][0], expected_p)
    assert h["p"][0].sum() == pytest.approx(10.0)
    np.testing.assert_allclose(h["c"][0], [0.5, 0.5, 0.5, 0.5, 1, 1, 1, 0, 0, 0, 0, 0, 0])


def test_to_hourly_dewpoint_below_temperature_when_dry():
    h = to_hourly([0, 3], [_step(298.15, 50), _step(298.15, 50, (0, 3))], horizon=3)
    # 25 °C at 50% humidity is about a 13.9 °C dewpoint.
    assert h["td"][0, 0] == pytest.approx(13.9, abs=0.1)


def _missing(url):
    request = httpx.Request("GET", url)
    return httpx.HTTPStatusError(
        "404", request=request, response=httpx.Response(404, request=request)
    )


def test_latest_initializations_skips_runs_still_uploading():
    available = {"2026100900", "2026100818", "2026100812"}

    def fetch(url, byte_range):
        if any(f"gefs.{s[:8]}/{s[8:]}/" in url for s in available):
            return b"ok"
        raise _missing(url)

    p = GefsProvider(fetch=fetch)
    inits = p.latest_initializations(2, now=datetime(2026, 10, 9, 8, 30, tzinfo=UTC))
    assert inits == [datetime(2026, 10, 9, 0, tzinfo=UTC), datetime(2026, 10, 8, 18, tzinfo=UTC)]


def test_latest_initializations_raises_when_nothing_is_published():
    def fetch(url, byte_range):
        raise _missing(url)

    with pytest.raises(ProviderUnavailable):
        GefsProvider(fetch=fetch).latest_initializations(1, now=datetime(2026, 10, 9, tzinfo=UTC))


def test_get_forecast_reads_grib_byte_ranges_end_to_end():
    eccodes = pytest.importorskip("eccodes")

    def message(value: float) -> bytes:
        gid = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
        for key, v in {
            "Ni": 720,
            "Nj": 361,
            "latitudeOfFirstGridPointInDegrees": 90,
            "longitudeOfFirstGridPointInDegrees": 0,
            "latitudeOfLastGridPointInDegrees": -90,
            "longitudeOfLastGridPointInDegrees": 359.5,
            "iDirectionIncrementInDegrees": 0.5,
            "jDirectionIncrementInDegrees": 0.5,
        }.items():
            eccodes.codes_set(gid, key, v)
        eccodes.codes_set_values(gid, np.full(361 * 720, value))
        try:
            return eccodes.codes_get_message(gid)
        finally:
            eccodes.codes_release(gid)

    def grib_file(step: int, member: int) -> tuple[str, bytes]:
        fields = [
            ("HGT", "10 mb", "", 0.0),
            ("TMP", "2 m above ground", "", 290.15 + member + step / 6),
            ("RH", "2 m above ground", "", 100.0),
            ("UGRD", "10 m above ground", "", 3.0),
            ("VGRD", "10 m above ground", "", 4.0),
        ]
        if step:
            fields += [
                ("APCP", "surface", f"0-{step} hour acc", 6.0 * member),
                ("TCDC", "entire atmosphere", f"0-{step} hour ave", 40.0),
            ]
        blob, idx = b"", []
        for n, (var, level, kind, value) in enumerate(fields, 1):
            idx.append(
                f"{n}:{len(blob)}:d=2026100900:{var}:{level}:{kind or f'{step} hour'} fcst:ENS=+{member}"
            )
            blob += message(value)
        return "\n".join(idx) + "\n", blob

    files = {}
    for m, name in enumerate(["gec00", "gep01"]):
        for step in (0, 6):
            idx, blob = grib_file(step, m)
            base = f"https://s3.test/gefs.20261009/00/atmos/pgrb2ap5/{name}.t00z.pgrb2a.0p50.f{step:03d}"
            files[base + ".idx"], files[base] = idx.encode(), blob

    requests = []

    def fetch(url, byte_range):
        requests.append((url, byte_range))
        body = files[url]
        if byte_range is None:
            return body
        lo, hi = byte_range
        return body[lo : None if hi is None else hi + 1]

    p = GefsProvider(base_url="https://s3.test", fetch=fetch, workers=2)
    p.member_names, p.steps, p.horizon_hours = ["gec00", "gep01"], [0, 6], 6
    gp = GridPointRef(uuid.uuid4(), "114:1115", 28.5, -81.25, "America/New_York")
    fc = p.get_forecast([gp], datetime(2026, 10, 9, tzinfo=UTC))[gp.id]

    assert fc.temperature_c.shape == (2, 7)
    np.testing.assert_allclose(fc.temperature_c[:, 0], [17.0, 18.0], atol=0.01)
    np.testing.assert_allclose(fc.temperature_c[:, 6], [18.0, 19.0], atol=0.01)
    np.testing.assert_allclose(fc.dewpoint_c, fc.temperature_c, atol=0.01)
    np.testing.assert_allclose(fc.wind_u_mps, 3.0, atol=0.01)
    # Member 1's 6 mm over hours 1–6, 1 mm each; the control stays dry.
    np.testing.assert_allclose(fc.precip_mm[1, 1:], 1.0, atol=0.01)
    np.testing.assert_allclose(fc.precip_mm[0], 0.0, atol=0.01)
    np.testing.assert_allclose(fc.cloud_cover, 0.4, atol=0.01)
    assert fc.valid_times[-1] == datetime(2026, 10, 9, 6, tzinfo=UTC)
    # The HGT message before the wanted fields is never downloaded.
    assert all(r[1] is None or r[1][0] > 0 for r in requests)

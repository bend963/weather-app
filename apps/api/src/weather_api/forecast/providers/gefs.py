"""NOAA GEFS provider: the 31-member Global Ensemble Forecast System.

A stand-in for WeatherNext until that access is granted, so the app can run on
real ensemble forecasts. GEFS is free and public on AWS (s3://noaa-gefs-pds),
published every 6 hours (00, 06, 12, 18 UTC) on a 0.5° grid out to 16 days.

How a run is read:

* Every member (gec00 control + gep01–gep30) has one GRIB2 file per forecast
  step: 3-hourly to 72 h, then 6-hourly to 360 h (the horizon used here).
* Each file has a `.idx` sidecar listing every field's byte offset, so only the
  six fields we need are downloaded, with one ranged GET per file. That is
  about 2,600 small requests per run, done in parallel (roughly 1.5 minutes).
* Values are bilinearly interpolated from the 0.5° grid to each grid point.
  The app's grid stays at 0.25° (see weather_api.grid), so switching to
  WeatherNext later keeps the same grid identifiers.
* Steps are filled in to hourly the way the rest of the app expects:
  temperature, humidity and wind are interpolated linearly; precipitation
  (accumulated over buckets that reset every 6 hours) is de-accumulated and
  spread evenly over the hours of its bucket; cloud cover (averaged over the
  same buckets) is de-averaged likewise. Dewpoint comes from temperature and
  relative humidity (Magnus formula).

Decoding GRIB needs the `eccodes` package (the `gefs` extra). Each call to
get_forecast downloads the run again, so ingestion's batches of 100 points
each cost one download; that is fine at personal-app scale.
"""

import logging
import re
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import numpy as np

from weather_api.forecast.providers.base import (
    EnsembleForecast,
    ForecastProvider,
    GridPointRef,
    ProviderUnavailable,
)

log = logging.getLogger(__name__)

BASE_URL = "https://noaa-gefs-pds.s3.amazonaws.com"
MEMBERS = ["gec00"] + [f"gep{i:02d}" for i in range(1, 31)]
HORIZON_HOURS = 360
STEPS = list(range(0, 73, 3)) + list(range(78, HORIZON_HOURS + 1, 6))
CYCLE_HOURS = 6

# (idx variable, idx level) -> our short name.
FIELDS: dict[tuple[str, str], str] = {
    ("TMP", "2 m above ground"): "t",
    ("RH", "2 m above ground"): "rh",
    ("UGRD", "10 m above ground"): "u",
    ("VGRD", "10 m above ground"): "v",
    ("APCP", "surface"): "tp",
    ("TCDC", "entire atmosphere"): "tcc",
}
# Bucketed fields carry "a-b hour acc fcst" / "a-b hour ave fcst" in the idx.
_BUCKET = re.compile(r"(\d+)-(\d+) hour (?:acc|ave)")

# The 0.5° global grid: 361 latitudes from 90 to -90, 720 longitudes from 0 east.
_NLAT, _NLON, _RES = 361, 720, 0.5

# fetch(url, (first_byte, last_byte or None for "to the end")) -> body
Fetch = Callable[[str, tuple[int, int | None] | None], bytes]


@dataclass(frozen=True)
class IdxField:
    name: str  # our short name, e.g. "t"
    start: int  # byte offset of the GRIB message
    end: int | None  # last byte (inclusive); None for the file's final message
    bucket: tuple[int, int] | None  # (start, end) hours for accumulated / averaged fields


def parse_idx(text: str) -> list[IdxField]:
    """The wanted fields from a GEFS .idx file, with their byte ranges."""
    rows = [line.split(":") for line in text.strip().splitlines()]
    starts = [int(r[1]) for r in rows]
    fields = []
    for i, r in enumerate(rows):
        name = FIELDS.get((r[3], r[4]))
        if name is None:
            continue
        m = _BUCKET.search(r[5]) if len(r) > 5 else None
        fields.append(
            IdxField(
                name=name,
                start=starts[i],
                end=starts[i + 1] - 1 if i + 1 < len(starts) else None,
                bucket=(int(m.group(1)), int(m.group(2))) if m else None,
            )
        )
    return fields


def bilinear_weights(latitude: float, longitude: float) -> list[tuple[int, int, float]]:
    """(row, column, weight) of the four 0.5° grid nodes around a point."""
    i = (90.0 - latitude) / _RES
    j = (longitude % 360.0) / _RES
    i0, j0 = min(int(np.floor(i)), _NLAT - 2), int(np.floor(j))
    di, dj = i - i0, j - j0
    j1 = (j0 + 1) % _NLON
    return [
        (i0, j0, (1 - di) * (1 - dj)),
        (i0 + 1, j0, di * (1 - dj)),
        (i0, j1, (1 - di) * dj),
        (i0 + 1, j1, di * dj),
    ]


@dataclass
class StepValues:
    """One member's fields at one step, already sampled at each grid point (arrays of length P)."""

    instant: dict[str, np.ndarray]  # t (K), rh (%), u, v (m/s)
    buckets: dict[str, tuple[tuple[int, int], np.ndarray]]  # tp (kg/m²), tcc (%)


def to_hourly(
    steps: Sequence[int], values: Sequence[StepValues], horizon: int = HORIZON_HOURS
) -> dict[str, np.ndarray]:
    """One member's step values as hourly (P, horizon + 1) arrays in SI units.

    Returns t (°C), td (°C), u, v (m/s), p (mm in the hour ending at each hour)
    and c (0–1).
    """
    points = len(next(iter(values[0].instant.values())))
    hours = np.arange(horizon + 1, dtype=float)
    st = np.asarray(steps, dtype=float)

    def interp(name: str) -> np.ndarray:
        series = np.stack([v.instant[name] for v in values], axis=1)  # (P, S)
        return np.stack([np.interp(hours, st, row) for row in series])

    t = interp("t") - 273.15
    rh = np.clip(interp("rh"), 1.0, 100.0)
    a, b = 17.625, 243.04
    gamma = np.log(rh / 100.0) + a * t / (b + t)
    td = b * gamma / (a - gamma)

    precip = np.zeros((points, horizon + 1))
    cloud = np.zeros((points, horizon + 1))
    # Within a bucket, each later step's value covers more hours; the
    # difference from the previous step is what fell (or the mean cloud) since then.
    seen: dict[int, tuple[int, np.ndarray, np.ndarray]] = {}
    for v in values:
        if "tp" not in v.buckets or "tcc" not in v.buckets:
            continue
        (start, end), tp = v.buckets["tp"]
        _, tcc = v.buckets["tcc"]
        tcc = tcc / 100.0
        if start in seen:
            prev_end, prev_tp, prev_tcc = seen[start]
            amount = tp - prev_tp
            mean_cloud = (tcc * (end - start) - prev_tcc * (prev_end - start)) / (end - prev_end)
            lo = prev_end
        else:
            amount, mean_cloud, lo = tp, tcc, start
        seen[start] = (end, tp, tcc)
        hi = min(end, horizon)
        if hi <= lo:
            continue
        precip[:, lo + 1 : hi + 1] = (np.maximum(amount, 0.0) / (end - lo))[:, None]
        cloud[:, lo + 1 : hi + 1] = np.clip(mean_cloud, 0.0, 1.0)[:, None]
    cloud[:, 0] = cloud[:, 1]
    return {"t": t, "td": td, "u": interp("u"), "v": interp("v"), "p": precip, "c": cloud}


def _http_fetch(client: httpx.Client) -> Fetch:
    def fetch(url: str, byte_range: tuple[int, int | None] | None = None) -> bytes:
        headers = {}
        if byte_range:
            headers["Range"] = (
                f"bytes={byte_range[0]}-{'' if byte_range[1] is None else byte_range[1]}"
            )
        for attempt in range(6):
            try:
                r = client.get(url, headers=headers)
                r.raise_for_status()
                return r.content
            except httpx.HTTPError:
                if attempt == 5:
                    raise
                time.sleep(2**attempt)
        raise AssertionError("unreachable")

    return fetch


class GefsProvider(ForecastProvider):
    model_name = "noaa_gefs"
    horizon_hours = HORIZON_HOURS
    member_names = MEMBERS
    steps = STEPS

    def __init__(
        self, base_url: str = BASE_URL, workers: int = 24, fetch: Fetch | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.workers = workers
        self._fetch = fetch or _http_fetch(httpx.Client(timeout=60.0, follow_redirects=True))

    def _url(self, init: datetime, member: str, step: int) -> str:
        cycle = f"{init.hour:02d}"
        return (
            f"{self.base_url}/gefs.{init:%Y%m%d}/{cycle}/atmos/pgrb2ap5/"
            f"{member}.t{cycle}z.pgrb2a.0p50.f{step:03d}"
        )

    def _complete(self, init: datetime) -> bool:
        # The last member's last step is uploaded last.
        try:
            self._fetch(self._url(init, self.member_names[-1], self.steps[-1]) + ".idx", None)
            return True
        except httpx.HTTPError:
            return False

    def latest_initializations(self, count: int = 1, now: datetime | None = None) -> list[datetime]:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        cycle = now.replace(
            hour=now.hour - now.hour % CYCLE_HOURS, minute=0, second=0, microsecond=0
        )
        found: list[datetime] = []
        # NOAA keeps a few weeks online; look back far enough to cover a backfill.
        for _ in range(count + 8):
            if self._complete(cycle):
                found.append(cycle)
                if len(found) == count:
                    break
            cycle -= timedelta(hours=CYCLE_HOURS)
        if not found:
            raise ProviderUnavailable("no complete GEFS run found on NOAA's S3 bucket")
        return found

    def get_forecast(
        self,
        grid_points: Sequence[GridPointRef],
        initialization_time: datetime | None = None,
    ) -> dict[UUID, EnsembleForecast]:
        if not grid_points:
            return {}
        try:
            import eccodes  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise ProviderUnavailable(
                "GEFS needs the eccodes package (install the 'gefs' extra)"
            ) from exc

        init = initialization_time or self.latest_initializations(1)[0]
        weights = [bilinear_weights(gp.latitude, gp.longitude) for gp in grid_points]
        started = time.monotonic()
        jobs = [(member, step) for member in self.member_names for step in self.steps]
        with ThreadPoolExecutor(self.workers) as pool:
            results = list(
                pool.map(lambda job: self._read_step(init, job[0], job[1], weights), jobs)
            )
        log.info(
            "gefs run downloaded",
            extra={
                "init": init.isoformat(),
                "points": len(grid_points),
                "seconds": round(time.monotonic() - started),
            },
        )

        n = len(self.steps)
        per_member = [results[m * n : (m + 1) * n] for m in range(len(self.member_names))]
        hourly = [to_hourly(self.steps, values, self.horizon_hours) for values in per_member]
        hours = np.arange(self.horizon_hours + 1, dtype=float)
        valid_times = [init + timedelta(hours=int(h)) for h in hours]
        out: dict[UUID, EnsembleForecast] = {}
        for p, gp in enumerate(grid_points):
            out[gp.id] = EnsembleForecast(
                valid_times=valid_times,
                lead_time_hours=hours,
                temperature_c=np.stack([h["t"][p] for h in hourly]),
                dewpoint_c=np.stack([h["td"][p] for h in hourly]),
                wind_u_mps=np.stack([h["u"][p] for h in hourly]),
                wind_v_mps=np.stack([h["v"][p] for h in hourly]),
                precip_mm=np.stack([h["p"][p] for h in hourly]),
                cloud_cover=np.stack([h["c"][p] for h in hourly]),
            )
        return out

    def _read_step(
        self, init: datetime, member: str, step: int, weights: list[list[tuple[int, int, float]]]
    ) -> StepValues:
        import eccodes

        url = self._url(init, member, step)
        fields = parse_idx(self._fetch(url + ".idx", None).decode())
        missing = {"t", "rh", "u", "v"} - {f.name for f in fields}
        if missing:
            raise ProviderUnavailable(f"GEFS {member} f{step:03d} lacks {sorted(missing)}")
        lo = min(f.start for f in fields)
        # One request spanning every wanted message (to the end of the file if one is last).
        hi = (
            None
            if any(f.end is None for f in fields)
            else max(f.end for f in fields if f.end is not None)
        )
        blob = self._fetch(url, (lo, hi))

        result = StepValues(instant={}, buckets={})
        for f in fields:
            end = len(blob) if f.end is None else f.end - lo + 1
            gid = eccodes.codes_new_from_message(blob[f.start - lo : end])
            try:
                grid = eccodes.codes_get_values(gid).reshape(_NLAT, _NLON)
            finally:
                eccodes.codes_release(gid)
            sampled = np.array([sum(grid[i, j] * w for i, j, w in ws) for ws in weights])
            if f.bucket is None:
                result.instant[f.name] = sampled
            else:
                result.buckets[f.name] = (f.bucket, sampled)
        return result

    def describe(self) -> dict[str, object]:
        return {
            "provider": type(self).__name__,
            "model": self.model_name,
            "source": f"{self.base_url} (pgrb2ap5)",
            "members": len(self.member_names),
        }

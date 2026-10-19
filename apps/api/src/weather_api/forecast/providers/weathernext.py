"""Google DeepMind WeatherNext 3, read from BigQuery.

Access comes through a BigQuery Analytics Hub listing: subscribing links the
WeatherNext tables into a dataset in your own Cloud project
(WEATHERNEXT_BIGQUERY_DATASET, either "dataset" in GOOGLE_CLOUD_PROJECT or
"project.dataset"). Queries run, and are billed, in GOOGLE_CLOUD_PROJECT.

The table used is `weathernext_3_0_0_0p1deg`, as Google documents it:

* one row per 0.1° cell per initialization: `init_time` (partition key),
  `geography` (the cell's centre point, the clustering key), and
  `geography_polygon`;
* `forecast`, a repeated record with one element per hourly step: `time`
  (valid time), `hours` (lead time, 1–360 for the 00/06/12/18 UTC runs), and
  each variable as `<name>_mean`, `_p10`, `_p25`, `_p50`, `_p75`, `_p90`.

Percentiles, not members: the table publishes statistics across the 64-member
ensemble rather than the members themselves (those are only in Google's Zarr
archive, stored one global field per step, which is far too costly to read
point by point). The percentiles are turned into spread paths (see
weather_api.forecast.spread_paths), and the forecasts are marked
from_percentiles so the UI labels them as spread rather than members.

Variables read: temperature_2m and dewpoint_temperature_2m (K -> °C),
wind_speed_10m and the mean u/v components (m/s), total_precipitation_1hr
(m per hour ending at `time` -> mm), total_cloud_cover (0–1).

Runs: only the 6-hourly runs (15-day horizon) are used; the hourly interim runs
only reach 48 hours. Google says a run is in BigQuery about 8 h 10 min after
its init time; latest_initializations() checks which runs are actually there.

Cost: BigQuery bills by bytes read. Every query filters on one `init_time`
partition, reads only the columns above, and filters cells with ST_DWITHIN on
`geography` so clustering can skip blocks. WEATHERNEXT_MAX_BYTES_BILLED caps
each query; a query over the cap fails without being charged.

Credentials: WEATHERNEXT_SA_KEY (a service-account JSON key, kept in a secret
store, never in the repo) or, if unset, Application Default Credentials.

Terms: real-time WeatherNext data comes under Google's experimental data terms,
which require a disclaimer and Google's copyright notice wherever it is shown;
the web app adds both when the model is WeatherNext.
"""

import json
import logging
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

import numpy as np

from weather_api.forecast.providers.base import (
    EnsembleForecast,
    ForecastProvider,
    GridPointRef,
    ProviderUnavailable,
)
from weather_api.forecast.spread_paths import precipitation_paths, spread_paths, wind_paths

log = logging.getLogger(__name__)

TABLE = "weathernext_3_0_0_0p1deg"
ENSEMBLE_SIZE = 64
HORIZON_HOURS = 360
CYCLE_HOURS = 6
#: Google: a 6-hourly run lands in BigQuery about 8 h 10 min after its init time.
PUBLISH_DELAY = timedelta(hours=8, minutes=10)
#: Cells within this distance of a grid node are candidates; the nearest wins.
#: Half a 0.1° cell's diagonal is under 8 km, so this always finds one.
SEARCH_RADIUS_M = 10_000

PERCENTILES = ("p10", "p25", "p50", "p75", "p90")
# Our short name -> the table's variable name, and which statistics are read.
VARIABLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "t": ("temperature_2m", PERCENTILES),
    "td": ("dewpoint_temperature_2m", PERCENTILES),
    "ws": ("wind_speed_10m", PERCENTILES),
    "u": ("u_component_of_wind_10m", ("mean",)),
    "v": ("v_component_of_wind_10m", ("mean",)),
    "tp": ("total_precipitation_1hr", (*PERCENTILES, "mean")),
    "tcc": ("total_cloud_cover", PERCENTILES),
}
COLUMNS = [f"{name}_{stat}" for name, stats in VARIABLES.values() for stat in stats]

K_TO_C = 273.15
M_TO_MM = 1000.0


class _Client(Protocol):
    def query(self, query: str, job_config: Any = None) -> Any: ...


def forecast_sql(table: str, point_count: int) -> str:
    """The forecast query for `point_count` grid nodes (parameters @lat0, @lon0, ...)."""
    near = "\n      OR ".join(
        f"ST_DWITHIN(t.geography, ST_GEOGPOINT(@lon{i}, @lat{i}), @radius_m)"
        for i in range(point_count)
    )
    nodes = ",\n    ".join(
        f"STRUCT(@id{i} AS id, ST_GEOGPOINT(@lon{i}, @lat{i}) AS pt)" for i in range(point_count)
    )
    fields = ",\n        ".join(f"f.{c}" for c in COLUMNS)
    picked = ",\n  ".join(f"s.{c}" for c in COLUMNS)
    return f"""
WITH nodes AS (
  SELECT * FROM UNNEST([
    {nodes}
  ])
),
cells AS (
  SELECT
    n.id,
    ARRAY(
      SELECT AS STRUCT
        f.time,
        f.hours,
        {fields}
      FROM UNNEST(t.forecast) AS f
      WHERE f.hours <= @horizon
    ) AS steps
  FROM `{table}` AS t
  JOIN nodes AS n ON ST_DWITHIN(t.geography, n.pt, @radius_m)
  WHERE t.init_time = @init_time
    AND ({near})
  QUALIFY ROW_NUMBER() OVER (PARTITION BY n.id ORDER BY ST_DISTANCE(t.geography, n.pt)) = 1
)
SELECT
  c.id,
  s.time,
  s.hours,
  {picked}
FROM cells AS c, UNNEST(c.steps) AS s
ORDER BY c.id, s.hours
"""


def inits_sql(table: str) -> str:
    return f"""
SELECT DISTINCT init_time
FROM `{table}`
WHERE init_time IN UNNEST(@candidates)
ORDER BY init_time DESC
"""


def forecasts_from_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, EnsembleForecast]:
    """Query rows (one per node and step) -> spread-path forecasts by node id."""
    by_node: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_node[str(row["id"])].append(row)

    out: dict[str, EnsembleForecast] = {}
    for node, steps in by_node.items():
        steps.sort(key=lambda r: r["hours"])
        values = {
            c: np.array([np.nan if r[c] is None else float(r[c]) for r in steps]) for c in COLUMNS
        }
        if any(np.isnan(v).any() for v in values.values()):
            log.warning("weathernext cell has missing values; skipped", extra={"node": node})
            continue

        out[node] = _spread_forecast(steps, values)
    return out


def _spread_forecast(
    steps: list[Mapping[str, Any]], values: dict[str, np.ndarray]
) -> EnsembleForecast:
    def pct(var: str, scale: float = 1.0, offset: float = 0.0) -> np.ndarray:
        name = VARIABLES[var][0]
        return np.stack([values[f"{name}_{p}"] for p in PERCENTILES]) * scale + offset

    def mean(var: str) -> np.ndarray:
        return values[f"{VARIABLES[var][0]}_mean"]

    u, v = wind_paths(pct("ws"), mean("u"), mean("v"))
    return EnsembleForecast(
        valid_times=[_utc(r["time"]) for r in steps],
        lead_time_hours=np.array([int(r["hours"]) for r in steps]),
        temperature_c=spread_paths(pct("t", offset=-K_TO_C)),
        dewpoint_c=spread_paths(pct("td", offset=-K_TO_C)),
        wind_u_mps=u,
        wind_v_mps=v,
        precip_mm=precipitation_paths(pct("tp", scale=M_TO_MM), mean("tp") * M_TO_MM),
        cloud_cover=spread_paths(pct("tcc"), lower=0.0, upper=1.0),
        from_percentiles=True,
        ensemble_size=ENSEMBLE_SIZE,
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class WeatherNextProvider(ForecastProvider):
    model_name = "weathernext_3"
    horizon_hours = HORIZON_HOURS

    def __init__(
        self,
        project: str | None,
        dataset: str | None,
        *,
        credentials_json: str | None = None,
        max_bytes_billed: int | None = None,
        client: _Client | None = None,
    ) -> None:
        self.project = project
        self.dataset = dataset
        self.credentials_json = credentials_json
        self.max_bytes_billed = max_bytes_billed
        self._bq: _Client | None = client

    @property
    def table(self) -> str:
        if not self.dataset:
            raise ProviderUnavailable("WEATHERNEXT_BIGQUERY_DATASET is not set")
        dataset = self.dataset if "." in self.dataset else f"{self.project}.{self.dataset}"
        return f"{dataset}.{TABLE}"

    def _client(self) -> _Client:
        if self._bq is not None:
            return self._bq
        if not self.project or not self.dataset:
            raise ProviderUnavailable(
                "WeatherNext is not configured: set GOOGLE_CLOUD_PROJECT and "
                "WEATHERNEXT_BIGQUERY_DATASET"
            )
        try:
            from google.cloud import bigquery  # optional dependency: weather-api[weathernext]
        except ImportError as exc:  # pragma: no cover - depends on install extras
            raise ProviderUnavailable(
                "google-cloud-bigquery is not installed (install weather-api[weathernext])"
            ) from exc
        credentials = None
        if self.credentials_json:
            from google.oauth2 import service_account

            try:
                info = json.loads(self.credentials_json)
            except ValueError as exc:
                raise ProviderUnavailable("WEATHERNEXT_SA_KEY is not valid JSON") from exc
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/bigquery"]
            )
        self._bq = bigquery.Client(project=self.project, credentials=credentials)
        return self._bq

    def _run(self, sql: str, params: list[Any]) -> list[Mapping[str, Any]]:
        from google.cloud import bigquery

        config = bigquery.QueryJobConfig(
            query_parameters=params,
            maximum_bytes_billed=self.max_bytes_billed,
        )
        started = time.monotonic()
        try:
            job = self._client().query(sql, job_config=config)
            rows = list(job.result())
        except ProviderUnavailable:
            raise
        except Exception as exc:  # google.api_core errors: auth, quota, bytes cap, ...
            raise ProviderUnavailable(f"WeatherNext query failed: {exc}") from exc
        log.info(
            "weathernext query",
            extra={
                "bytes_billed": getattr(job, "total_bytes_billed", None),
                "rows": len(rows),
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
        return rows

    def latest_initializations(self, count: int = 1, now: datetime | None = None) -> list[datetime]:
        from google.cloud import bigquery

        now = (now or datetime.now(UTC)).astimezone(UTC)
        newest = now - PUBLISH_DELAY
        newest = newest.replace(
            hour=newest.hour - newest.hour % CYCLE_HOURS, minute=0, second=0, microsecond=0
        )
        # A few extra cycles in case the newest runs are late.
        candidates = [newest - timedelta(hours=CYCLE_HOURS * i) for i in range(count + 4)]
        rows = self._run(
            inits_sql(self.table),
            [bigquery.ArrayQueryParameter("candidates", "TIMESTAMP", candidates)],
        )
        found = sorted((_utc(r["init_time"]) for r in rows), reverse=True)[:count]
        if not found:
            raise ProviderUnavailable("no recent WeatherNext 3 run found in BigQuery")
        return found

    def get_forecast(
        self,
        grid_points: Sequence[GridPointRef],
        initialization_time: datetime | None = None,
    ) -> dict[UUID, EnsembleForecast]:
        if not grid_points:
            return {}
        from google.cloud import bigquery

        init = initialization_time or self.latest_initializations(1)[0]
        params: list[Any] = [
            bigquery.ScalarQueryParameter("init_time", "TIMESTAMP", init),
            bigquery.ScalarQueryParameter("horizon", "INT64", self.horizon_hours),
            bigquery.ScalarQueryParameter("radius_m", "FLOAT64", float(SEARCH_RADIUS_M)),
        ]
        for i, gp in enumerate(grid_points):
            params += [
                bigquery.ScalarQueryParameter(f"id{i}", "STRING", str(gp.id)),
                bigquery.ScalarQueryParameter(f"lat{i}", "FLOAT64", gp.latitude),
                bigquery.ScalarQueryParameter(f"lon{i}", "FLOAT64", gp.longitude),
            ]
        rows = self._run(forecast_sql(self.table, len(grid_points)), params)
        by_id = forecasts_from_rows(rows)
        return {gp.id: by_id[str(gp.id)] for gp in grid_points if str(gp.id) in by_id}

    def available(self) -> bool:
        return self._bq is not None or bool(self.project and self.dataset)

    def describe(self) -> dict[str, object]:
        return {
            **super().describe(),
            "source": f"BigQuery {TABLE}",
            "dataset": self.dataset,
            "statistics": "percentiles",
            "members": ENSEMBLE_SIZE,
        }

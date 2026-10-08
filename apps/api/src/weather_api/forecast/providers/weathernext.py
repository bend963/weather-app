"""Google DeepMind WeatherNext provider (BigQuery).

Status: interface only. Access to the WeatherNext datasets has not been granted
yet, so the table layout cannot be inspected. Rather than guess at an
undocumented schema, this class defines exactly what the rest of the system
needs and fails clearly until the two TODOs below are filled in.

What the implementation must do (nothing outside this file should change):

1. latest_initializations(): query the dataset for the most recent
   initialization times that are fully published, newest first.
2. get_forecast(): for the requested grid nodes and one initialization, fetch
   every ensemble member's hourly (or native-step) values for:
       2 m temperature, 2 m dewpoint, 10 m u/v wind, precipitation,
       total cloud cover
   and return them as EnsembleForecast arrays in SI units:
       temperature K -> °C, precipitation m -> mm (per hour ending at
       valid_time; de-accumulate if the source is cumulative), cloud 0–1.

Notes for whoever implements it:

* Query only the active grid nodes passed in (WHERE on the grid identifier or
  lat/lon list). Never scan the globe; BigQuery bills by bytes scanned, so
  select only the needed columns and partitions (init time).
* If the dataset's native time step is coarser than 1 hour (e.g. 6 h),
  either store native steps (the hourly table tolerates gaps) or interpolate
  temperature/wind and distribute precipitation. Document the choice here.
* Grid identifiers come from weather_api.grid; confirm resolution and the
  longitude convention match the dataset (see the TODO there).
* Credentials come from Application Default Credentials: the Cloud Run
  service account in production, GOOGLE_APPLICATION_CREDENTIALS locally.
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from weather_api.forecast.providers.base import (
    EnsembleForecast,
    ForecastProvider,
    GridPointRef,
    ProviderUnavailable,
)


class WeatherNextProvider(ForecastProvider):
    model_name = "weathernext"
    horizon_hours = 360  # TODO(weathernext): confirm from dataset metadata.

    def __init__(self, project: str | None, dataset: str | None) -> None:
        self.project = project
        self.dataset = dataset

    def _client(self):  # type: ignore[no-untyped-def]
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
        return bigquery.Client(project=self.project)

    def latest_initializations(self, count: int = 1, now: datetime | None = None) -> list[datetime]:
        self._client()
        # TODO(weathernext): SELECT DISTINCT init_time ... ORDER BY init_time DESC LIMIT @count
        # against the granted dataset, once its schema can be inspected.
        raise ProviderUnavailable("WeatherNext initialization lookup is not implemented yet")

    def get_forecast(
        self,
        grid_points: Sequence[GridPointRef],
        initialization_time: datetime | None = None,
    ) -> dict[UUID, EnsembleForecast]:
        self._client()
        # TODO(weathernext): parameterized query for these grid nodes and this
        # init time, then reshape rows into EnsembleForecast arrays (members, T).
        raise ProviderUnavailable("WeatherNext forecast retrieval is not implemented yet")

    def available(self) -> bool:
        # TODO(weathernext): return bool(self.project and self.dataset) once
        # the two methods above are implemented.
        return False

    def describe(self) -> dict[str, object]:
        return {**super().describe(), "dataset": self.dataset}

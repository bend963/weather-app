"""The contract every forecast source implements.

Providers return raw ensemble members on the shared grid, in SI units. They know
nothing about the database, users, or how statistics are computed; ingestion
turns members into the normalized hourly/daily tables. Adding ECMWF or GFS later
means writing one more class with these two methods.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import numpy as np


class ProviderUnavailable(RuntimeError):
    """The forecast source cannot be reached or is not configured."""


@dataclass(frozen=True)
class GridPointRef:
    id: UUID
    model_grid_identifier: str
    latitude: float
    longitude: float
    timezone: str


@dataclass
class EnsembleForecast:
    """All ensemble members for one grid point and one model run.

    Every array has shape (members, len(valid_times)). Deterministic (single
    member) sources use members = 1; statistics then collapse to that value and
    probabilities become 0 or 1.
    """

    valid_times: list[datetime]  # UTC, hourly
    lead_time_hours: np.ndarray  # (T,)
    temperature_c: np.ndarray  # 2 m air temperature
    dewpoint_c: np.ndarray  # 2 m dewpoint
    wind_u_mps: np.ndarray  # 10 m eastward wind
    wind_v_mps: np.ndarray  # 10 m northward wind
    precip_mm: np.ndarray  # accumulation over the hour ending at valid_time
    cloud_cover: np.ndarray  # total cloud fraction, 0–1

    @property
    def member_count(self) -> int:
        return int(self.temperature_c.shape[0])


class ForecastProvider(ABC):
    #: Stored as forecast_runs.model. Distinct per source so runs never mix.
    model_name: str
    #: Hours from initialization to the last forecast step.
    horizon_hours: int

    @abstractmethod
    def latest_initializations(self, count: int = 1, now: datetime | None = None) -> list[datetime]:
        """The most recent `count` model initializations available, newest first."""

    @abstractmethod
    def get_forecast(
        self,
        grid_points: Sequence[GridPointRef],
        initialization_time: datetime | None = None,
    ) -> dict[UUID, EnsembleForecast]:
        """Ensemble forecasts for each grid point, keyed by grid point id.

        initialization_time=None means the latest available run.
        """

    def available(self) -> bool:
        """False when the source is known to be unusable (e.g. not configured)."""
        return True

    def describe(self) -> dict[str, object]:
        """Metadata recorded on forecast_runs.source_metadata."""
        return {"provider": type(self).__name__, "model": self.model_name}

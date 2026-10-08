"""Deterministic synthetic ensemble forecasts for development and tests.

The mock behaves like a real ensemble system so the whole application can be
built and exercised without WeatherNext credentials:

* A model run is issued every 12 hours (00Z and 12Z) and becomes available a
  few hours later, mirroring operational latency.
* Each grid point has a seeded "true" weather evolution: climatology by
  latitude and season, a diurnal cycle tied to local solar time, and passing
  weather systems (sums of multi-day waves) that drive temperature,
  moisture, cloud and rain together.
* Each run carries its own error relative to that truth, growing with lead
  time, so successive runs for the same target converge as it approaches. This
  is what makes the forecast-history view meaningful with mock data.
* Ensemble members diverge from the run's central forecast with spread that
  grows with lead time, so uncertainty widens through the forecast.

Every random draw is seeded from (grid identifier, initialization time), so the
same request always yields the same numbers.
"""

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import numpy as np

from weather_api.forecast.providers.base import EnsembleForecast, ForecastProvider, GridPointRef

CYCLE_HOURS = 12
AVAILABILITY_LAG_HOURS = 5


def _seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:16], 16)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _waves(
    t: np.ndarray, periods: np.ndarray, phases: np.ndarray, amps: Sequence[float]
) -> np.ndarray:
    """Sum of sinusoids. t may be (T,) or broadcast against (M, 1) parameters."""
    total = np.zeros(np.broadcast_shapes(t.shape, periods[..., 0].shape))
    for k, amp in enumerate(amps):
        total = total + amp * np.sin(2 * np.pi * t / periods[..., k] + phases[..., k])
    return total


class MockForecastProvider(ForecastProvider):
    model_name = "mock_weathernext"

    def __init__(self, members: int = 50, horizon_hours: int = 360) -> None:
        self.members = members
        self.horizon_hours = horizon_hours

    def latest_initializations(self, count: int = 1, now: datetime | None = None) -> list[datetime]:
        now = now or datetime.now(UTC)
        available = now - timedelta(hours=AVAILABILITY_LAG_HOURS)
        latest = available.replace(
            hour=available.hour - available.hour % CYCLE_HOURS, minute=0, second=0, microsecond=0
        )
        return [latest - timedelta(hours=CYCLE_HOURS * i) for i in range(count)]

    def get_forecast(
        self,
        grid_points: Sequence[GridPointRef],
        initialization_time: datetime | None = None,
    ) -> dict[UUID, EnsembleForecast]:
        init = initialization_time or self.latest_initializations(1)[0]
        return {gp.id: self._forecast_for(gp, init) for gp in grid_points}

    def describe(self) -> dict[str, object]:
        return {**super().describe(), "members": self.members, "synthetic": True}

    def _forecast_for(self, gp: GridPointRef, init: datetime) -> EnsembleForecast:
        lead = np.arange(self.horizon_hours + 1, dtype=np.float64)
        valid_times = [init + timedelta(hours=int(h)) for h in lead]
        t_abs = init.timestamp() / 3600.0 + lead  # hours since epoch
        days = lead / 24.0
        lat, lon = gp.latitude, gp.longitude
        M = self.members

        point = np.random.default_rng(_seed("point", gp.model_grid_identifier))
        run = np.random.default_rng(_seed("run", gp.model_grid_identifier, init.isoformat()))
        mem = np.random.default_rng(_seed("members", gp.model_grid_identifier, init.isoformat()))

        # --- Climatology: warmer toward the equator, seasons flip by hemisphere.
        annual_mean = 29.5 - 0.45 * max(abs(lat) - 12.0, 0.0)
        seasonal_amp = 1.0 + 0.22 * abs(lat)
        day_of_year = (t_abs / 24.0) % 365.2425
        hemisphere = 1.0 if lat >= 0 else -1.0
        climatology = annual_mean + hemisphere * seasonal_amp * np.cos(
            2 * np.pi * (day_of_year - 200) / 365.25
        )

        # Local solar time drives the diurnal cycle; highs around 3 PM.
        solar_hour = ((t_abs % 24) + lon / 15.0) % 24
        diurnal = np.cos(2 * np.pi * (solar_hour - 15.0) / 24.0)
        afternoon = np.maximum(np.cos(2 * np.pi * (solar_hour - 16.0) / 24.0), 0.0)

        # --- The point's "true" weather systems (independent of the run).
        temp_truth = _waves(
            t_abs, point.uniform(70, 160, 3), point.uniform(0, 2 * np.pi, 3), (2.5, 1.5, 1.0)
        )
        wet_truth = (
            _waves(
                t_abs, point.uniform(50, 130, 3), point.uniform(0, 2 * np.pi, 3), (0.7, 0.5, 0.3)
            )
            - 0.2
        )
        wind_base = point.uniform(2.5, 5.0)
        wind_truth = wind_base * (
            1 + 0.4 * np.sin(2 * np.pi * t_abs / point.uniform(40, 90) + point.uniform(0, 6.3))
        )
        prevailing_dir = point.uniform(0, 360)
        dir_truth = prevailing_dir + 70 * np.sin(
            2 * np.pi * t_abs / point.uniform(60, 140) + point.uniform(0, 6.3)
        )

        # --- This run's error: smooth in lead time, growing with lead.
        run_temp_err = (0.3 + 0.35 * np.sqrt(days)) * _waves(
            lead, run.uniform(40, 120, 2), run.uniform(0, 2 * np.pi, 2), (0.8, 0.6)
        )
        run_wet_err = (0.05 + 0.12 * np.sqrt(days)) * _waves(
            lead, run.uniform(30, 100, 2), run.uniform(0, 2 * np.pi, 2), (0.8, 0.6)
        )

        # --- Member perturbations: (M, T), spread grows with lead time.
        def member_noise(sigma: np.ndarray, white: float) -> np.ndarray:
            smooth = _waves(
                lead[None, :],
                mem.uniform(30, 120, (M, 1, 2)),
                mem.uniform(0, 2 * np.pi, (M, 1, 2)),
                (0.75, 0.65),
            )
            return sigma[None, :] * smooth + mem.normal(0, white, (M, lead.size))

        temp_pert = member_noise(0.3 + 0.55 * days**0.75, 0.25)
        wet_pert = member_noise(0.08 + 0.12 * days**0.75, 0.05)

        wet = wet_truth + run_wet_err + wet_pert  # (M, T)
        cloud = np.clip(_sigmoid(3.0 * (wet + 0.25)) + mem.normal(0, 0.06, wet.shape), 0.0, 1.0)

        # Clouds damp the diurnal range; rain-cooled air runs a little cooler.
        temperature = (
            climatology
            + 4.5 * diurnal * (1 - 0.6 * cloud)
            + temp_truth
            + run_temp_err
            + temp_pert
            - 1.2 * np.maximum(wet, 0.0)
        )
        # Moist air (high "wet") has a small dewpoint depression.
        depression = 1.0 + 9.0 * (1 - _sigmoid(2.5 * (wet + 0.1))) + 1.5 * np.maximum(diurnal, 0)
        dewpoint = np.minimum(temperature - depression, 27.0)

        # Rain when the moisture signal crosses a threshold; warm afternoons
        # favour convective boosts. Lognormal noise gives a skewed amount spread.
        convective = 1 + 0.5 * afternoon * (temperature > 20)
        rate = np.where(wet > 0.55, 2.0 * np.clip(wet - 0.55, 0, None) ** 1.4 * convective, 0.0)
        precip = rate * mem.lognormal(0.0, 0.4, wet.shape)

        speed = np.clip(
            wind_truth * (1 + mem.normal(0, 0.12 + 0.02 * days, (M, lead.size)))
            + 1.5 * np.clip(wet, 0, None),
            0.0,
            None,
        )
        direction = np.deg2rad(dir_truth + mem.normal(0, 10 + 4 * days, (M, lead.size)))
        # Meteorological convention: direction the wind blows *from*.
        u = -speed * np.sin(direction)
        v = -speed * np.cos(direction)

        f32 = np.float32
        return EnsembleForecast(
            valid_times=valid_times,
            lead_time_hours=lead.astype(np.int32),
            temperature_c=temperature.astype(f32),
            dewpoint_c=dewpoint.astype(f32),
            wind_u_mps=u.astype(f32),
            wind_v_mps=v.astype(f32),
            precip_mm=precip.astype(f32),
            cloud_cover=cloud.astype(f32),
        )

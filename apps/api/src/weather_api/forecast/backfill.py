"""Fill forecasts for a newly saved location's grid point right away.

Without this, a new grid point would have no forecast until the next scheduled
ingestion. Runs as a FastAPI background task after the response is sent; it
uses the same idempotent ingestion code as the Cloud Run Job, so racing with
the job is harmless.
"""

import logging
import threading
from datetime import datetime
from uuid import UUID

from weather_api.config import get_settings
from weather_api.db import session_scope
from weather_api.forecast.ingestion import run_ingestion
from weather_api.forecast.providers import ForecastProvider, ProviderUnavailable

log = logging.getLogger(__name__)

_in_flight: set[UUID] = set()
_lock = threading.Lock()


def ensure_point_forecast(
    grid_point_id: UUID, provider: ForecastProvider, now: datetime | None = None
) -> None:
    with _lock:
        if grid_point_id in _in_flight:
            return
        _in_flight.add(grid_point_id)
    try:
        if not provider.available():
            return
        with session_scope() as session:
            run_ingestion(
                session,
                provider,
                backfill_runs=get_settings().ingestion_backfill_runs,
                grid_point_ids=[grid_point_id],
                now=now,
            )
    except ProviderUnavailable:
        log.warning(
            "forecast provider unavailable during backfill",
            extra={"grid_point_id": str(grid_point_id), "provider": provider.model_name},
        )
    except Exception:
        log.exception("grid point backfill failed", extra={"grid_point_id": str(grid_point_id)})
    finally:
        with _lock:
            _in_flight.discard(grid_point_id)

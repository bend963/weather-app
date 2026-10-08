"""Structured JSON logging, compatible with Google Cloud Logging.

Cloud Logging parses one JSON object per line and maps "severity" and
"message". Extra fields (request_id, forecast_run_id, grid_point_id, provider,
duration_ms, status, error_category) become structured payload fields.

Never log coordinates, cookies or request bodies.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_STRUCTURED_FIELDS = (
    "request_id",
    "forecast_run_id",
    "grid_point_id",
    "provider",
    "duration_ms",
    "status",
    "status_code",
    "error_category",
    "method",
    "route",
    "points",
    "runs",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        for key in _STRUCTURED_FIELDS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Uvicorn's access log would print full URLs and client addresses; the
    # request middleware logs a sanitized line instead.
    logging.getLogger("uvicorn.access").disabled = True

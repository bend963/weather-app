"""forecast-ingestion: ingest the latest model runs for active grid points.

    forecast-ingestion run [--backfill-runs N]
    forecast-ingestion deactivate-unused [--days N]
    forecast-ingestion migrate

Exit status is non-zero if any run failed, so Cloud Run Jobs retries and
alerting see the failure.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from weather_api.config import get_settings
from weather_api.db import session_scope
from weather_api.forecast.ingestion import deactivate_unused_grid_points, run_ingestion
from weather_api.forecast.providers import ProviderUnavailable, get_forecast_provider
from weather_api.logging_config import configure_logging

log = logging.getLogger("forecast_ingestion")


def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    provider = get_forecast_provider()
    if not provider.available():
        log.error(
            "forecast provider unavailable",
            extra={"provider": provider.model_name, "error_category": "provider_unavailable"},
        )
        return 2
    backfill = args.backfill_runs or settings.ingestion_backfill_runs
    try:
        with session_scope() as session:
            report = run_ingestion(session, provider, backfill_runs=backfill)
    except ProviderUnavailable:
        log.exception("forecast provider unavailable", extra={"provider": provider.model_name})
        return 2
    print(json.dumps(report.as_dict(), default=str))
    return 1 if report.failed else 0


def _deactivate(args: argparse.Namespace) -> int:
    days = args.days or get_settings().grid_point_inactive_days
    with session_scope() as session:
        count = deactivate_unused_grid_points(session, days)
    log.info("deactivated unused grid points", extra={"points": count})
    return 0


def _migrate(_: argparse.Namespace) -> int:
    import weather_api
    from alembic import command
    from alembic.config import Config

    # alembic.ini sits next to src/ in the API package (copied into the image).
    candidates = [
        Path(weather_api.__file__).resolve().parents[2] / "alembic.ini",
        Path("/app/apps/api/alembic.ini"),
    ]
    ini = next((p for p in candidates if p.exists()), None)
    if ini is None:
        log.error("alembic.ini not found")
        return 2
    command.upgrade(Config(str(ini)), "head")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="forecast-ingestion")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="ingest the latest model runs")
    run.add_argument("--backfill-runs", type=int, default=None)
    run.set_defaults(func=_run)
    deactivate = sub.add_parser("deactivate-unused", help="stop ingesting unreferenced grid points")
    deactivate.add_argument("--days", type=int, default=None)
    deactivate.set_defaults(func=_deactivate)
    migrate = sub.add_parser("migrate", help="apply database migrations")
    migrate.set_defaults(func=_migrate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

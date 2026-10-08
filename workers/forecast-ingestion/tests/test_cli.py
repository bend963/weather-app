import json

from forecast_ingestion.__main__ import main
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from weather_api.db import get_engine
from weather_api.locations import get_or_create_grid_point
from weather_api.models import ForecastRun, HourlyForecast


def _reset() -> None:
    with get_engine().begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))


def test_migrate_then_run_twice_is_idempotent(capsys):
    _reset()
    assert main(["migrate"]) == 0
    with Session(get_engine()) as session:
        get_or_create_grid_point(session, 28.5, -81.3)
        session.commit()

    assert main(["run", "--backfill-runs", "2"]) == 0
    report = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert [r["status"] for r in report["runs"]] == ["complete", "complete"]

    with Session(get_engine()) as session:
        rows = session.scalar(select(func.count()).select_from(HourlyForecast))
        assert session.scalar(select(func.count()).select_from(ForecastRun)) == 2

    assert main(["run", "--backfill-runs", "2"]) == 0
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(HourlyForecast)) == rows

    assert main(["deactivate-unused", "--days", "30"]) == 0
    _reset()


def test_unavailable_provider_exits_nonzero(monkeypatch):
    from weather_api.config import get_settings
    from weather_api.forecast import providers

    monkeypatch.setattr(get_settings(), "forecast_provider", "weathernext")
    providers.get_forecast_provider.cache_clear()
    try:
        assert main(["run"]) == 2
    finally:
        providers.get_forecast_provider.cache_clear()

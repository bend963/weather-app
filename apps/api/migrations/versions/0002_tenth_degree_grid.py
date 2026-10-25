"""Move saved locations from the 0.25° grid to WeatherNext 3's 0.1° grid.

WeatherNext 3 publishes on a 0.1° grid, so grid points are now 0.1° nodes
(model_name "weathernext_0p1"; see weather_api.grid). Each saved location is
re-snapped from its own coordinate, exactly as normalize_to_grid does, and
pointed at the new node. The new nodes start with no forecasts; the next
ingestion fills them. Old 0.25° nodes are deactivated, not deleted, so their
forecast history is kept.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19 23:50:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _move_to(model: str, resolution: str, nodes_around: int) -> None:
    # Same arithmetic as weather_api.grid.normalize_to_grid: round half away
    # from zero, longitude index wrapped onto [0, nodes_around).
    lat_index = f"round(sl.latitude / {resolution})::int"
    lon_index = f"((round(sl.longitude / {resolution})::int % {nodes_around}) + {nodes_around}) % {nodes_around}"
    op.execute(
        f"""
        INSERT INTO weather_grid_points
            (latitude, longitude, model_name, model_grid_identifier, timezone)
        SELECT DISTINCT ON (c.identifier)
            c.lat_index * {resolution},
            CASE WHEN c.lon_index * {resolution} >= 180
                 THEN c.lon_index * {resolution} - 360
                 ELSE c.lon_index * {resolution} END,
            '{model}',
            c.identifier,
            c.timezone
        FROM (
            SELECT {lat_index} AS lat_index,
                   {lon_index} AS lon_index,
                   {lat_index} || ':' || {lon_index} AS identifier,
                   gp.timezone
            FROM saved_locations sl
            JOIN weather_grid_points gp ON gp.id = sl.weather_grid_point_id
        ) c
        ORDER BY c.identifier
        ON CONFLICT ON CONSTRAINT uq_grid_points_identifier
        DO UPDATE SET active = true, last_requested_at = now()
        """
    )
    op.execute(
        f"""
        UPDATE saved_locations sl
        SET weather_grid_point_id = gp.id
        FROM weather_grid_points gp
        WHERE gp.model_name = '{model}'
          AND gp.model_grid_identifier = {lat_index} || ':' || {lon_index}
        """
    )
    op.execute(f"UPDATE weather_grid_points SET active = false WHERE model_name <> '{model}'")


def upgrade() -> None:
    _move_to("weathernext_0p1", "0.1", 3600)


def downgrade() -> None:
    _move_to("weathernext_0p25", "0.25", 1440)

"""Initial schema: ownership tables plus shared forecast tables.

See weather_api/models.py for the reasoning behind each table.

Revision ID: 0001
Revises:
Create Date: 2026-10-08 00:35:54.910508
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("initialization_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("forecast_horizon_hours", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'complete', 'failed')",
            name="ck_forecast_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model", "initialization_time", name="uq_forecast_runs_model_init"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "visitors",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "weather_grid_points",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("model_grid_identifier", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("elevation_m", sa.REAL(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "model_name", "model_grid_identifier", name="uq_grid_points_identifier"
        ),
    )
    op.create_index(
        "ix_grid_points_active",
        "weather_grid_points",
        ["active"],
        unique=False,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "daily_forecasts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("weather_grid_point_id", sa.UUID(), nullable=False),
        sa.Column("forecast_run_id", sa.UUID(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("high_p50_c", sa.REAL(), nullable=False),
        sa.Column("high_p10_c", sa.REAL(), nullable=True),
        sa.Column("high_p90_c", sa.REAL(), nullable=True),
        sa.Column("low_p50_c", sa.REAL(), nullable=False),
        sa.Column("low_p10_c", sa.REAL(), nullable=True),
        sa.Column("low_p90_c", sa.REAL(), nullable=True),
        sa.Column("precip_probability", sa.REAL(), nullable=True),
        sa.Column("precip_p50_mm", sa.REAL(), nullable=True),
        sa.Column("precip_p90_mm", sa.REAL(), nullable=True),
        sa.Column("wind_max_p50_mps", sa.REAL(), nullable=True),
        sa.Column("wind_max_p90_mps", sa.REAL(), nullable=True),
        sa.Column("confidence_score", sa.REAL(), nullable=True),
        sa.Column("temperature_agreement", sa.REAL(), nullable=True),
        sa.Column("precip_agreement", sa.REAL(), nullable=True),
        sa.Column("raw_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["forecast_run_id"],
            ["forecast_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["weather_grid_point_id"],
            ["weather_grid_points.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "weather_grid_point_id", "forecast_run_id", "local_date", name="uq_daily_point_run_date"
        ),
    )
    op.create_index(
        "ix_daily_point_date",
        "daily_forecasts",
        ["weather_grid_point_id", "local_date"],
        unique=False,
    )
    op.create_table(
        "hourly_forecasts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("weather_grid_point_id", sa.UUID(), nullable=False),
        sa.Column("forecast_run_id", sa.UUID(), nullable=False),
        sa.Column("forecast_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_time_hours", sa.Integer(), nullable=False),
        sa.Column("temperature_p10_c", sa.REAL(), nullable=True),
        sa.Column("temperature_p50_c", sa.REAL(), nullable=False),
        sa.Column("temperature_p90_c", sa.REAL(), nullable=True),
        sa.Column("dewpoint_p50_c", sa.REAL(), nullable=True),
        sa.Column("wind_speed_p50_mps", sa.REAL(), nullable=True),
        sa.Column("wind_speed_p90_mps", sa.REAL(), nullable=True),
        sa.Column("wind_direction_deg", sa.REAL(), nullable=True),
        sa.Column("precip_probability", sa.REAL(), nullable=True),
        sa.Column("precip_p50_mm", sa.REAL(), nullable=True),
        sa.Column("precip_p90_mm", sa.REAL(), nullable=True),
        sa.Column("cloud_cover_p50", sa.REAL(), nullable=True),
        sa.Column("confidence_score", sa.REAL(), nullable=True),
        sa.Column("raw_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["forecast_run_id"],
            ["forecast_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["weather_grid_point_id"],
            ["weather_grid_points.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "weather_grid_point_id",
            "forecast_run_id",
            "forecast_time",
            name="uq_hourly_point_run_time",
        ),
    )
    op.create_index(
        "ix_hourly_point_time",
        "hourly_forecasts",
        ["weather_grid_point_id", "forecast_time"],
        unique=False,
    )
    op.create_table(
        "saved_locations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("visitor_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("weather_grid_point_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("elevation_m", sa.REAL(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(visitor_id IS NULL) <> (user_id IS NULL)", name="ck_saved_locations_one_owner"
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_saved_locations_latitude"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_saved_locations_longitude"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visitor_id"], ["visitors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["weather_grid_point_id"],
            ["weather_grid_points.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_saved_locations_grid_point", "saved_locations", ["weather_grid_point_id"], unique=False
    )
    op.create_index("ix_saved_locations_user", "saved_locations", ["user_id"], unique=False)
    op.create_index("ix_saved_locations_visitor", "saved_locations", ["visitor_id"], unique=False)
    op.create_index(
        "uq_saved_locations_default_user",
        "saved_locations",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_saved_locations_default_visitor",
        "saved_locations",
        ["visitor_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND visitor_id IS NOT NULL"),
    )
    op.create_table(
        "visitor_preferences",
        sa.Column("visitor_id", sa.UUID(), nullable=False),
        sa.Column("temperature_unit", sa.Text(), server_default="F", nullable=False),
        sa.Column("precipitation_unit", sa.Text(), server_default="in", nullable=False),
        sa.Column("wind_unit", sa.Text(), server_default="mph", nullable=False),
        sa.Column(
            "show_advanced_forecast", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("precipitation_unit IN ('in', 'mm')", name="ck_pref_precip_unit"),
        sa.CheckConstraint("temperature_unit IN ('F', 'C')", name="ck_pref_temperature_unit"),
        sa.CheckConstraint("wind_unit IN ('mph', 'kmh', 'mps', 'kt')", name="ck_pref_wind_unit"),
        sa.ForeignKeyConstraint(["visitor_id"], ["visitors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("visitor_id"),
    )


def downgrade() -> None:
    op.drop_table("visitor_preferences")
    op.drop_index(
        "uq_saved_locations_default_visitor",
        table_name="saved_locations",
        postgresql_where=sa.text("is_default AND visitor_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_saved_locations_default_user",
        table_name="saved_locations",
        postgresql_where=sa.text("is_default AND user_id IS NOT NULL"),
    )
    op.drop_index("ix_saved_locations_visitor", table_name="saved_locations")
    op.drop_index("ix_saved_locations_user", table_name="saved_locations")
    op.drop_index("ix_saved_locations_grid_point", table_name="saved_locations")
    op.drop_table("saved_locations")
    op.drop_index("ix_hourly_point_time", table_name="hourly_forecasts")
    op.drop_table("hourly_forecasts")
    op.drop_index("ix_daily_point_date", table_name="daily_forecasts")
    op.drop_table("daily_forecasts")
    op.drop_index(
        "ix_grid_points_active",
        table_name="weather_grid_points",
        postgresql_where=sa.text("active"),
    )
    op.drop_table("weather_grid_points")
    op.drop_table("visitors")
    op.drop_table("users")
    op.drop_table("forecast_runs")

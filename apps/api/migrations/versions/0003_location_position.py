"""Let each owner put their saved locations in their own order.

Adds saved_locations.position. Existing rows are numbered in the order the
list showed them before (default first, then oldest first).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30 19:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "saved_locations",
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.execute(
        """
        UPDATE saved_locations sl SET position = ranked.n
        FROM (
            SELECT id, row_number() OVER (
                PARTITION BY coalesce(visitor_id, user_id)
                ORDER BY is_default DESC, created_at, id
            ) - 1 AS n
            FROM saved_locations
        ) ranked
        WHERE sl.id = ranked.id
        """
    )


def downgrade() -> None:
    op.drop_column("saved_locations", "position")

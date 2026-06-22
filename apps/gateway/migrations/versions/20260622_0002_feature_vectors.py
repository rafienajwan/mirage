"""Add ML feature-vector storage to events."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260622_0002"
down_revision: Union[str, None] = "20260622_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "feature_vector",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("events", "feature_vector")

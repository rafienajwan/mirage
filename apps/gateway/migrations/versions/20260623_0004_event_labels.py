"""Add analyst labels to events."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260623_0004"
down_revision: Union[str, None] = "20260623_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("analyst_label", sa.String(32), nullable=True))
    op.add_column(
        "events",
        sa.Column(
            "analyst_note",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "events",
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("events", "labeled_at")
    op.drop_column("events", "analyst_note")
    op.drop_column("events", "analyst_label")

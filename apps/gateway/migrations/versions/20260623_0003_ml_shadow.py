"""Add ML shadow scoring metadata to events."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260623_0003"
down_revision: Union[str, None] = "20260622_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("ml_shadow", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "ml_shadow")

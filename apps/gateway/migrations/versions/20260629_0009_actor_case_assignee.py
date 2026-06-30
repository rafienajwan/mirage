"""Add actor case assignee."""

from alembic import op
import sqlalchemy as sa

revision = "20260629_0009"
down_revision = "20260629_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "actor_cases",
        sa.Column("assigned_to", sa.String(length=120), nullable=False, server_default=""),
    )
    op.create_index("ix_actor_cases_assigned_to", "actor_cases", ["assigned_to"])


def downgrade() -> None:
    op.drop_index("ix_actor_cases_assigned_to", table_name="actor_cases")
    op.drop_column("actor_cases", "assigned_to")

"""Add persisted actor cases."""

from alembic import op
import sqlalchemy as sa

revision = "20260629_0008"
down_revision = "20260628_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "actor_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("cluster_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("actor_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actor_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("recommended_action", sa.String(length=512), nullable=False),
        sa.Column("analyst_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_actor_cases_case_id", "actor_cases", ["case_id"], unique=True)
    op.create_index("ix_actor_cases_cluster_id", "actor_cases", ["cluster_id"])
    op.create_index("ix_actor_cases_severity", "actor_cases", ["severity"])
    op.create_index("ix_actor_cases_status", "actor_cases", ["status"])
    op.create_index("ix_actor_cases_last_seen", "actor_cases", ["last_seen"])


def downgrade() -> None:
    op.drop_index("ix_actor_cases_last_seen", table_name="actor_cases")
    op.drop_index("ix_actor_cases_status", table_name="actor_cases")
    op.drop_index("ix_actor_cases_severity", table_name="actor_cases")
    op.drop_index("ix_actor_cases_cluster_id", table_name="actor_cases")
    op.drop_index("ix_actor_cases_case_id", table_name="actor_cases")
    op.drop_table("actor_cases")

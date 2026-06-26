"""Add honeytoken hit tracking."""

from alembic import op
import sqlalchemy as sa

revision = "20260626_0005"
down_revision = "20260623_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "honeytoken_hits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hit_id", sa.String(length=32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_id", sa.String(length=32), nullable=False),
        sa.Column("token_kind", sa.String(length=32), nullable=False),
        sa.Column("token_label", sa.String(length=128), nullable=False),
        sa.Column("source_ip", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("evidence", sa.String(length=256), nullable=False),
    )
    op.create_index("ix_honeytoken_hits_hit_id", "honeytoken_hits", ["hit_id"])
    op.create_index("ix_honeytoken_hits_event_id", "honeytoken_hits", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_honeytoken_hits_event_id", table_name="honeytoken_hits")
    op.drop_index("ix_honeytoken_hits_hit_id", table_name="honeytoken_hits")
    op.drop_table("honeytoken_hits")

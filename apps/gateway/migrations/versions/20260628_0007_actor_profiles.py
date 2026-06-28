"""Add persistent actor profiles."""

from alembic import op
import sqlalchemy as sa

revision = "20260628_0007"
down_revision = "20260626_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "actor_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.String(length=32), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("source_ip", sa.String(length=64), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suspicious_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decoy_redirects", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("honeytoken_hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_risk_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_risk_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("path_counts", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_decision", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_actor_profiles_actor_id", "actor_profiles", ["actor_id"], unique=True)
    op.create_index("ix_actor_profiles_fingerprint_hash", "actor_profiles", ["fingerprint_hash"])
    op.create_index("ix_actor_profiles_last_seen", "actor_profiles", ["last_seen"])


def downgrade() -> None:
    op.drop_index("ix_actor_profiles_last_seen", table_name="actor_profiles")
    op.drop_index("ix_actor_profiles_fingerprint_hash", table_name="actor_profiles")
    op.drop_index("ix_actor_profiles_actor_id", table_name="actor_profiles")
    op.drop_table("actor_profiles")

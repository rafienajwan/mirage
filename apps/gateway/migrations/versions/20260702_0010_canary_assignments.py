"""Add canary assignment lifecycle records."""

from alembic import op
import sqlalchemy as sa

revision = "20260702_0010"
down_revision = "20260629_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canary_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assignment_id", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=32), nullable=False),
        sa.Column("token_kind", sa.String(length=32), nullable=False),
        sa.Column("token_label", sa.String(length=128), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("rotation_epoch", sa.String(length=64), nullable=False),
        sa.Column("decoy_type", sa.String(length=32), nullable=False),
        sa.Column("source_path", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=240), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id"),
    )
    op.create_index(
        "ix_canary_assignments_actor_id",
        "canary_assignments",
        ["actor_id"],
    )
    op.create_index(
        "ix_canary_assignments_assignment_id",
        "canary_assignments",
        ["assignment_id"],
    )
    op.create_index(
        "ix_canary_assignments_last_seen_at",
        "canary_assignments",
        ["last_seen_at"],
    )
    op.create_index(
        "ix_canary_assignments_rotation_epoch",
        "canary_assignments",
        ["rotation_epoch"],
    )
    op.create_index(
        "ix_canary_assignments_status",
        "canary_assignments",
        ["status"],
    )
    op.create_index(
        "ix_canary_assignments_token_hash",
        "canary_assignments",
        ["token_hash"],
    )
    op.create_index(
        "ix_canary_assignments_token_kind",
        "canary_assignments",
        ["token_kind"],
    )


def downgrade() -> None:
    op.drop_index("ix_canary_assignments_token_kind", table_name="canary_assignments")
    op.drop_index("ix_canary_assignments_token_hash", table_name="canary_assignments")
    op.drop_index("ix_canary_assignments_status", table_name="canary_assignments")
    op.drop_index("ix_canary_assignments_rotation_epoch", table_name="canary_assignments")
    op.drop_index("ix_canary_assignments_last_seen_at", table_name="canary_assignments")
    op.drop_index("ix_canary_assignments_assignment_id", table_name="canary_assignments")
    op.drop_index("ix_canary_assignments_actor_id", table_name="canary_assignments")
    op.drop_table("canary_assignments")

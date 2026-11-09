"""Add operator accounts, the operator audit trail, and attribution columns."""

from alembic import op
import sqlalchemy as sa

revision = "20261109_0011"
down_revision = "20260702_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operators",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_operators_username", "operators", ["username"], unique=True)

    op.create_table(
        "operator_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("operator", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("target", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("detail", sa.String(length=500), nullable=False, server_default=""),
    )
    op.create_index("ix_operator_audit_occurred_at", "operator_audit", ["occurred_at"])
    op.create_index("ix_operator_audit_operator", "operator_audit", ["operator"])

    op.add_column("events", sa.Column("labeled_by", sa.String(length=32), nullable=True))
    op.add_column("actor_cases", sa.Column("updated_by", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("actor_cases", "updated_by")
    op.drop_column("events", "labeled_by")
    op.drop_index("ix_operator_audit_operator", table_name="operator_audit")
    op.drop_index("ix_operator_audit_occurred_at", table_name="operator_audit")
    op.drop_table("operator_audit")
    op.drop_index("ix_operators_username", table_name="operators")
    op.drop_table("operators")

"""Persist event fingerprints for actor profiles."""

from alembic import op
import sqlalchemy as sa

revision = "20260626_0006"
down_revision = "20260626_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "fingerprint_hash",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
    )
    op.create_index("ix_events_fingerprint_hash", "events", ["fingerprint_hash"])


def downgrade() -> None:
    op.drop_index("ix_events_fingerprint_hash", table_name="events")
    op.drop_column("events", "fingerprint_hash")

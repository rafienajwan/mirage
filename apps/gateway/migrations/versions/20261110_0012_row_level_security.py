"""Enable row-level security on every MIRAGE table (PostgreSQL only).

Supabase publishes tables in the public schema through its Data API, and its
default grants let the browser-facing ``anon`` and ``authenticated`` roles
read them, operator password hashes included. With RLS on and no policies,
those roles see nothing. The gateway connects as the table owner, which RLS
does not restrict, so the application is unaffected. Plain PostgreSQL gains
the same default-deny for any non-owner role.
"""

from alembic import op

revision = "20261110_0012"
down_revision = "20261109_0011"
branch_labels = None
depends_on = None


def _set_row_level_security(enabled: bool) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    action = "ENABLE" if enabled else "DISABLE"
    op.execute(
        f"""
        DO $$
        DECLARE t record;
        BEGIN
          FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = current_schema() LOOP
            EXECUTE format('ALTER TABLE %I {action} ROW LEVEL SECURITY', t.tablename);
          END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    _set_row_level_security(True)


def downgrade() -> None:
    _set_row_level_security(False)

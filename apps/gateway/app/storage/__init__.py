"""Storage layer — exports the active store instance.

By default uses the async DatabaseStore (SQLite). Set DATABASE_URL to an
empty string to fall back to the synchronous MemoryStore.
"""

from __future__ import annotations

from app.core.config import settings

_db_url = settings.database_url

if _db_url and (
    _db_url.startswith("sqlite") or _db_url.startswith("postgresql")
):
    from app.storage.db.repository import DatabaseStore

    store = DatabaseStore()
else:
    from app.storage.memory_store import MemoryStore  # type: ignore[assignment]

    store = MemoryStore()  # type: ignore[assignment]

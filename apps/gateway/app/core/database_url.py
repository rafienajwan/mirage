"""Make a pasted PostgreSQL connection string usable by the asyncpg engine.

Supabase and most hosts hand out ``postgres://`` or ``postgresql://`` URLs
with ``sslmode=require``. SQLAlchemy would pick the psycopg2 driver for the
first, the store selector would not recognise ``postgres://`` at all, and
asyncpg rejects ``sslmode``. Only the scheme and query are rewritten, as
plain strings, so a URL-encoded password is never decoded or re-encoded.
"""

from __future__ import annotations

_PLAIN_SCHEMES = ("postgres://", "postgresql://")
_ASYNCPG_SCHEME = "postgresql+asyncpg://"


def _rewrite_query(query: str) -> str:
    pairs = [pair for pair in query.split("&") if pair]
    if not any(pair.partition("=")[0] == "sslmode" for pair in pairs):
        return query
    has_ssl = any(pair.partition("=")[0] == "ssl" for pair in pairs)
    rewritten = []
    for pair in pairs:
        key, _, value = pair.partition("=")
        if key == "sslmode":
            if has_ssl:
                continue
            pair = f"ssl={value}"
        rewritten.append(pair)
    return "&".join(rewritten)


def normalize_database_url(url: str) -> str:
    """Return ``url`` with the asyncpg scheme and ``ssl`` in place of ``sslmode``."""
    for scheme in _PLAIN_SCHEMES:
        if url.startswith(scheme):
            url = _ASYNCPG_SCHEME + url[len(scheme):]
            break
    if not url.startswith(_ASYNCPG_SCHEME):
        return url
    base, separator, query = url.partition("?")
    if not separator:
        return url
    query = _rewrite_query(query)
    return f"{base}?{query}" if query else base

"""Async database engine, session factory, and lifecycle helpers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.config import settings

# ── Engine ──────────────────────────────────────────────────────

_connect_args = {}
_pool_class = None

if settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
    _pool_class = StaticPool

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=_connect_args,
    **({"poolclass": _pool_class} if _pool_class else {}),
)

# ── Session factory ─────────────────────────────────────────────

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative base ────────────────────────────────────────────

class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# ── Session context manager ─────────────────────────────────────

@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an async session; auto-commit or rollback."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Lifecycle ────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables. Called once at application startup."""
    # Import models so they register with Base.metadata
    from app.storage.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose engine connections. Called at shutdown."""
    await engine.dispose()

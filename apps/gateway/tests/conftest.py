"""Shared test fixtures."""

import atexit
import os
from pathlib import Path
import shutil
import tempfile

from httpx import ASGITransport, AsyncClient
import pytest

# Configure storage before importing the application singleton. A file
# database (not :memory:) gives each session its own connection, matching
# production isolation.
_TEST_DB = Path(tempfile.mkdtemp(prefix="mirage-tests-")) / "test.db"
atexit.register(shutil.rmtree, _TEST_DB.parent, ignore_errors=True)
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
os.environ["MIRAGE_API_KEY"] = ""
# The rate limiter's per-IP window is process-global, so request-heavy tests
# would throttle each other depending on order. Tests that exercise rate
# limiting configure their own limit.
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"

from app.main import app  # noqa: E402
from app.storage.db.database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
async def setup_db():
    """Create fresh tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

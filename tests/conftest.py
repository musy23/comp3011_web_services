"""
Shared pytest fixtures.

Strategy:
- Set DATABASE_URL env var before any app import → app connects to uk_climate_test
- Patch the app's engine to use NullPool → no connection caching between event loops
- Use psycopg2 (sync) for DB setup/teardown → zero event loop conflicts
- Each async test gets its own event loop (default) → fine with NullPool
"""

import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@db:5432/uk_climate_test"
os.environ["DATABASE_URL_SYNC"] = "postgresql://postgres:postgres@db:5432/uk_climate_test"
os.environ["ADMIN_API_KEY"] = "local-dev-key"

import psycopg2  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import app.database as _db  # noqa: E402
import app.main as _main  # noqa: E402
from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402

_TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@db:5432/uk_climate_test"

# Patch the app's engine with NullPool so asyncpg never caches connections
# across different event loops (one per test function).
_test_engine = create_async_engine(_TEST_DB_URL, poolclass=NullPool, echo=False)
_db.engine = _test_engine
_db.AsyncSessionLocal = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False,
    autocommit=False, autoflush=False,
)
_main.engine = _test_engine  # patch lifespan reference


# ── Session-scoped DB setup (sync, no event loop) ────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create uk_climate_test database and schema once per session."""
    # Create database
    conn = psycopg2.connect("postgresql://postgres:postgres@db:5432/postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'uk_climate_test'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE uk_climate_test")
    cur.close()
    conn.close()

    # Create tables via a one-off event loop (outside pytest's loops)
    async def _create_tables():
        e = create_async_engine(_TEST_DB_URL, poolclass=NullPool)
        async with e.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await e.dispose()

    asyncio.run(_create_tables())
    yield


# ── Per-test truncation (sync) ───────────────────────────────────────────────

@pytest.fixture(autouse=True)
def truncate_tables(setup_test_db):
    """Wipe all rows before each test for clean isolation."""
    conn = psycopg2.connect("postgresql://postgres:postgres@db:5432/uk_climate_test")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "TRUNCATE TABLE user_annotations, observations, api_keys, stations "
        "RESTART IDENTITY CASCADE"
    )
    cur.close()
    conn.close()


# ── HTTP clients ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "local-dev-key"},
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def public_client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ── Shared payloads ──────────────────────────────────────────────────────────

STATION_PAYLOAD = {
    "station_id": "TESTST",
    "name": "Test Station",
    "region": "Test Region",
    "country": "UK",
    "latitude": 53.5,
    "longitude": -1.5,
    "elevation_m": 100,
    "opened_year": 1950,
}

OBSERVATION_PAYLOAD = {
    "date": "2023-06-15",
    "max_temp_c": 22.5,
    "min_temp_c": 11.3,
    "mean_temp_c": 16.9,
    "rainfall_mm": 3.2,
    "sunshine_hours": 8.5,
    "data_quality": 1,
}

ANNOTATION_PAYLOAD = {
    "observation_date": "2023-06-15",
    "note": "Unusually warm day for June — possible urban heat island effect.",
    "submitted_by": "test@example.com",
}

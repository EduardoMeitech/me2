"""Test fixtures for ME2 API tests.

Uses a real PostgreSQL test database (me2_test). Set TEST_DATABASE_URL
env var to override. Requires a running PostgreSQL instance.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Override database before importing app modules
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://me2:me2dev@localhost:5432/me2_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from api.core.database import Base, get_db  # noqa: E402
from api.core.models import (  # noqa: E402
    Alert,
    Equipment,
    Plant,
    ProductionEvent,
    StatusEvent,
    Tenant,
    User,
    UserRole,
)
from api.main import app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create tables in the test database."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Provide a transactional test session that rolls back after each test."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """Async HTTP test client with database session override."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_data(db_session):
    """Seed a tenant, plant, user, and equipment for testing."""
    tenant_id = str(uuid4())
    plant_id = str(uuid4())
    user_id = str(uuid4())
    equipment_id = str(uuid4())

    tenant = Tenant(id=tenant_id, name="Meitech Test", country="BRA")
    db_session.add(tenant)

    plant = Plant(id=plant_id, tenant_id=tenant_id, name="Planta Teste")
    db_session.add(plant)

    # bcrypt hash of "testpass123"
    import bcrypt
    pw_hash = bcrypt.hashpw("testpass123".encode(), bcrypt.gensalt()).decode()

    user = User(
        id=user_id,
        tenant_id=tenant_id,
        name="Test User",
        email="test@meitech.com.br",
        role=UserRole.meitech_admin,
        password_hash=pw_hash,
    )
    db_session.add(user)

    equip = Equipment(
        id=equipment_id,
        plant_id=plant_id,
        serial_number="MEI-TEST-0001",
        name="Teste Corte 01",
        model="M241",
        manufacturer="Schneider",
        standard_cycle_time_s=3.5,
    )
    db_session.add(equip)

    await db_session.flush()

    return {
        "tenant_id": tenant_id,
        "plant_id": plant_id,
        "user_id": user_id,
        "equipment_id": equipment_id,
        "email": "test@meitech.com.br",
        "password": "testpass123",
    }


@pytest_asyncio.fixture
async def auth_token(client, seed_data):
    """Login and return a valid JWT token."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_data["email"], "password": seed_data["password"]},
    )
    assert res.status_code == 200
    return res.json()["data"]["access_token"]


@pytest_asyncio.fixture
async def auth_headers(auth_token):
    """Return Authorization headers dict."""
    return {"Authorization": f"Bearer {auth_token}"}

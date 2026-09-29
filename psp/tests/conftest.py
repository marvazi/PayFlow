from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from psp.core.config import settings
from psp.db.session import get_session
from psp.main import app
from psp.models import Transaction


TEST_DATABASE_URL = (
    "postgresql+asyncpg://"
    "payflow_psp_test:payflow_psp_test_password"
    "@127.0.0.1:5436/payflow_psp_test"
)


@pytest_asyncio.fixture
async def psp_session_factory():
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def psp_client(psp_session_factory):
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        # Каждый HTTP-запрос получает собственную сессию.
        async with psp_session_factory() as session:
            yield session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_session] = override_get_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://psp.test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def psp_headers():
    return {"X-API-Key": settings.api_key}


@pytest_asyncio.fixture
async def tracked_payment_ids(psp_session_factory):
    """Удаляем только операции, созданные конкретным тестом."""
    payment_ids = []

    try:
        yield payment_ids
    finally:
        if payment_ids:
            async with psp_session_factory() as session:
                async with session.begin():
                    await session.execute(
                        delete(Transaction).where(
                            Transaction.external_payment_id.in_(payment_ids)
                        )
                    )


@pytest.fixture
def transaction_payload(tracked_payment_ids):
    from uuid import uuid4

    external_payment_id = uuid4()
    tracked_payment_ids.append(external_payment_id)

    return {
        "external_payment_id": str(external_payment_id),
        "amount_minor": 150050,
        "currency": "RUB",
    }
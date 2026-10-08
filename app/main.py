from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import router as auth_router
from app.api.customer import router as customer_router
from app.api.invoice import router as invoice_router
from app.api.organization import router as organization_router
from app.api.payment import router as payment_router
from app.cache.redis import RedisCache
from app.core.config import settings
from app.db.session import get_session


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1.0,
        socket_timeout=1.0,
    )
    app.state.cache = RedisCache(
        redis=redis_client,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )

    try:
        yield
    finally:
        await redis_client.aclose()


app = FastAPI(title="PayFlow", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(customer_router)
app.include_router(invoice_router)
app.include_router(payment_router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


@app.get("/health/db", tags=["health"])
async def check_database(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"database": "ok"}

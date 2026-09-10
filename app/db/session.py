from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker,AsyncSession
from collections.abc import AsyncIterator
from app.core.config import settings


engine = create_async_engine(settings.database_url,pool_pre_ping=True)
session_factory = async_sessionmaker(bind=engine,expire_on_commit=False)

async def get_session()-> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
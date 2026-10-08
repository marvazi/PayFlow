import secrets

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from psp.core.config import settings
from psp.db.session import get_session
from psp.services.transaction import TransactionService

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)


async def get_transaction_service(session: AsyncSession = Depends(get_session)):
    return TransactionService(session)


async def verify_api_key(api_key: str | None = Depends(api_key_header)):
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if not secrets.compare_digest(
        api_key.encode("utf-8"),
        settings.api_key.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный API-ключ",
        )

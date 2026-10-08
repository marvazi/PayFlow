from collections.abc import AsyncIterator

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import RedisCache
from app.core.config import settings
from app.core.exeptions import InvalidTokenError
from app.db.session import get_session, session_factory
from app.integrations.psp.client import PSPClient
from app.models import User
from app.services.customer import CustomerService
from app.services.invoice import InvoiceService
from app.services.membership import MembershipService
from app.services.organization import OrganizationService
from app.services.payment import PaymentService
from app.services.user import UserService


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)


bearer_scheme = HTTPBearer(auto_error=False)


def get_cache(request: Request) -> RedisCache:
    return request.app.state.cache


async def get_auth_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def get_psp_client() -> AsyncIterator[PSPClient]:
    async with httpx.AsyncClient(
        base_url=settings.psp_base_url,
        timeout=settings.psp_timeout_seconds,
        headers={"X-API-Key": settings.psp_api_key},
    ) as client:
        yield PSPClient(client=client)


def get_auth_user_service(
    session: AsyncSession = Depends(get_auth_session),
) -> UserService:
    return UserService(session)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user_service: UserService = Depends(get_auth_user_service),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Не удалось подтвердить авторизацию",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user = await user_service.get_current_user(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail="Не удалось подтвердить авторизацию",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return user


async def get_organization_service(
    session: AsyncSession = Depends(get_session),
) -> OrganizationService:
    return OrganizationService(session)


def get_member_service(
    session: AsyncSession = Depends(get_session),
) -> MembershipService:
    return MembershipService(session)


async def get_customer_service(
    session: AsyncSession = Depends(get_session),
    cache: RedisCache = Depends(get_cache),
) -> CustomerService:
    return CustomerService(session=session, cache=cache)


async def get_invoice_service(
    session: AsyncSession = Depends(get_session),
) -> InvoiceService:
    return InvoiceService(session)


async def get_payment_service(
    session: AsyncSession = Depends(get_session),
) -> PaymentService:
    return PaymentService(session)

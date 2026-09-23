from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, session
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials

from app.core.exeptions import InvalidTokenError
from app.db.session import get_session, session_factory
from app.models import User
from app.schemas.membership import MembershipResponse
from app.services.customer import CustomerService
from app.services.membership import MembershipService
from app.services.organization import OrganizationService
from app.services.user import UserService




def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)

bearer_scheme =HTTPBearer(auto_error=False)

async def get_auth_session()-> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session

def get_auth_user_service(session: AsyncSession = Depends(get_auth_session)) -> UserService:
    return UserService(session)


async def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        user_service: UserService = Depends(get_auth_user_service)
)->User:
    if credentials is None:
        raise HTTPException(status_code=401,detail="Не удалось подтвердить авторизацию", headers={"WWW-Authenticate": "Bearer"})
    try:
        user = await user_service.get_current_user(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401,detail="Не удалось подтвердить авторизацию", headers={"WWW-Authenticate": "Bearer"}) from exc

    return user

async def get_organization_service(session: AsyncSession = Depends(get_session)) -> OrganizationService:
    return OrganizationService(session)

def get_member_service(session: AsyncSession = Depends(get_session)) -> MembershipService:
    return MembershipService(session)

async def get_customer_service(session: AsyncSession = Depends(get_session)) -> CustomerService:
    return CustomerService(session)

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, session
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials

from app.core.exeptions import InvalidTokenError
from app.db.session import get_session
from app.models import User
from app.services.user import UserService


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)

bearer_scheme =HTTPBearer(auto_error=False)


async def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        user_service: UserService = Depends(get_user_service)
)->User:
    if credentials is None:
        raise HTTPException(status_code=401,detail="Не удалось подтвердить авторизацию", headers={"WWW-Authenticate": "Bearer"})
    try:
        user = await user_service.get_current_user(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401,detail="Не удалось подтвердить авторизацию", headers={"WWW-Authenticate": "Bearer"}) from exc

    return user
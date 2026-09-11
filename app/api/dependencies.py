from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, session

from app.db.session import get_session
from app.services.user import UserService


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)
    
from uuid import uuid4
from app.core.exeptions import EmailAlreadyExistsError
import pytest
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user import UserService
from app.tests.conftest import db_session
from app.core.security import verify_password


@pytest.mark.asyncio
async def test_register_user(db_session):
    user = UserCreate(name=" Максим ", email=f"{uuid4()}@example.com", password="123456757")#Подгтовил
    try:
        service = UserService(db_session)# Создал сервис
        await service.register(user) # Вызвал регистрацию
        user_result = await db_session.execute(
            select(User).where(User.email == user.email)
        ) # Нашел по имейл в бд
        result = user_result.scalar_one_or_none()
        assert result is not None # он найден
        assert result.name == user.name
        assert result.password_hash is not None
        assert result.password_hash != user.password
        assert verify_password(user.password, result.password_hash)

    finally:
        await db_session.rollback()

        await db_session.execute(
            delete(User).where(User.email == user.email)
        )
        await db_session.commit()
@pytest.mark.asyncio
async def test_register_with_same_email(db_session):
    user = UserCreate(name=" Максим ", email=f"{uuid4()}@example.com", password="123456757")
    try:
        service = UserService(db_session)
        await service.register(user)
        with pytest.raises(EmailAlreadyExistsError):
            await service.register(user)
        user_result = await db_session.execute(
            select(User).where(User.email == user.email)
        )
        users = user_result.scalars().all()
        assert len(users) == 1
    finally:
        await db_session.rollback()

        await db_session.execute(
            delete(User).where(User.email == user.email)
        )
        await db_session.commit()

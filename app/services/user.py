from asyncio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exeptions import EmailAlreadyExistsError
from app.core.security import hash_password
from app.models import User
from app.repositories.user import UserRepository
from sqlalchemy.exc import IntegrityError
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repository = UserRepository(session)


    async def register(self,data:UserCreate) -> User:
        password_hash = await to_thread(hash_password, data.password)
        try:
            async with self.session.begin():
                user = await self.user_repository.create(
                    name=data.name,
                    email=data.email,
                    password_hash = password_hash
                )
        except IntegrityError as exc:
            cause = exc.orig.__cause__

            if (
                    getattr(cause, "sqlstate", None) == "23505"
                    and getattr(cause, "constraint_name", None)
                    == "users_email_unique_idx"
            ):
                raise EmailAlreadyExistsError(
                    "Пользователь с таким email уже существует"
                ) from exc

            raise
        return user


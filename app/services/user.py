from asyncio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exeptions import EmailAlreadyExistsError, InvalidCredentialsError, InvalidTokenError
from app.core.security import hash_password, verify_password, decode_access_token
from app.models import User
from app.repositories.user import UserRepository
from sqlalchemy.exc import IntegrityError
from app.schemas.user import UserCreate, UserLogin


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


    async def authenticate(self,data: UserLogin) -> User:

        user = await self.user_repository.get_by_email(data.email)
        if user is None or user.password_hash is None:
            raise InvalidCredentialsError("Неверный email или пароль")
        checked_password = await to_thread(verify_password, data.password, user.password_hash)
        if not checked_password:
            raise InvalidCredentialsError("Неверный email или пароль")
        return user

    async def get_current_user(self,token:str) -> User:
        user_id = decode_access_token(token)
        current_user = await self.user_repository.get_by_id(user_id)
        if current_user is None:
            raise InvalidTokenError("Недействительный токен")
        return current_user







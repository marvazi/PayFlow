from datetime import datetime, timezone, timedelta
from uuid import UUID
import jwt
from pwdlib import PasswordHash
from app.core.config import settings
from app.core.exeptions import InvalidTokenError

password_hasher = PasswordHash.recommended()


def hash_password(password:str) -> str:
    return password_hasher.hash(password)

def verify_password(password:str, hashed_password:str) -> bool:
    return password_hasher.verify(password, hashed_password)

def create_access_token(user_id:UUID)->str:
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    encoded_jwt = jwt.encode(
        {"sub":str(user_id), "exp":exp},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
        res = UUID(payload["sub"])
        return res
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise InvalidTokenError("Недействительный токен") from exc

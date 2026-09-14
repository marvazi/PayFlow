import uuid

import jwt
from datetime import datetime, timezone, timedelta

import pytest

from app.core.config import settings
from app.core.exeptions import InvalidTokenError
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token


def test_correct_password():
    hashed_password = hash_password("Secret123")
    assert verify_password("Secret123", hashed_password)

def test_incorrect_password():
    hashed_password = hash_password("Secret123")
    assert not verify_password("Secret1232", hashed_password)


def test_correct_jwt_token():
    user_id  =uuid.uuid4()
    jwt_token = create_access_token(user_id )
    payload = jwt.decode(
        jwt_token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub","exp"]}
    )
    assert payload["sub"] == str(user_id)
    assert payload["exp"] >datetime.now(timezone.utc).timestamp()

def test_decode_access_token_rejects_expired_token():
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(InvalidTokenError) as exc_info:
        decode_access_token(token)

    assert isinstance(exc_info.value.__cause__, jwt.ExpiredSignatureError)
import secrets
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID

import jwt
import pytest
from sqlalchemy import delete

from app.core.config import settings
from app.core.exeptions import InvalidCredentialsError, InvalidTokenError
from app.core.security import create_access_token
from app.models import User
from app.schemas.user import UserCreate, UserLogin
from app.services.user import UserService


@pytest.mark.asyncio
async def test_auth_api(client):
    response = await client.post(
        "/auth/register",
        json={
            "name": "Максим",
            "email": "max@example.com",
            "password": "123",
        },
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_success_auth_api(client, db_session):
    email = f"{uuid4()}@example.com"
    password = "123456781"
    try:
        response = await client.post(
            "/auth/register",
            json={
                "name": "Максим",
                "email": email,
                "password": password,
            }
        )
        data = response.json()
        assert response.status_code == 201
        assert data["email"] == email
        assert data["id"] is not None
        assert "password" not in data
        assert "password_hash" not in data
    finally:
        await db_session.rollback()

        await db_session.execute(
            delete(User).where(User.email == email)
        )
        await db_session.commit()

@pytest.mark.asyncio
async def test_email_auth_api(client, db_session):
    email = f"{uuid4()}@example.com"
    try:
        response = await client.post(
            "/auth/register",
            json={
                'email': email,
                'password': '12345567859',
                'name': 'Max'
            }
        )
        assert response.status_code == 201

        one_more_response = await client.post(
            "/auth/register",
            json={
                'email': email,
                'password': '12345567859',
                'name': 'Max'
            }
        )

        assert one_more_response.status_code == 409
        assert one_more_response.json()["detail"] == (
            "Пользователь с таким email уже существует"
        )

    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(User).where(User.email == email)
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_authenticate_returns_registered_user( db_session):
    user = UserCreate(name="A", email=f"{uuid4()}@example.com", password="123456757")  # Подгтовил
    service = UserService(db_session)  # Создал сервис
    try:
        registered_user = await service.register(user)  # Вызвал регистрацию
        login_user = UserLogin(email=user.email, password=user.password)
        service_login_user = UserService(db_session)
        authenticated_user  = await service_login_user.authenticate(login_user)
        assert authenticated_user.id == registered_user.id
    finally:
        await db_session.rollback()

        await db_session.execute(
            delete(User).where(User.email == user.email)
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_authenticate_rejects_wrong_password(db_session):
    data = UserCreate(
        name="Максим",
        email=f"{uuid4()}@example.com",
        password="CorrectPassword123",
    )
    service = UserService(db_session)

    try:
        await service.register(data)

        login_data = UserLogin(
            email=data.email,
            password="WrongPassword123",
        )

        with pytest.raises(InvalidCredentialsError):
            await service.authenticate(login_data)
    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(User).where(User.email == data.email)
        )
        await db_session.commit()

@pytest.mark.asyncio
async def test_authenticate_success(client,db_session):
    email = f"{uuid4()}@example.com"
    password = "123456781"
    try:
        response = await client.post(
            "/auth/register",
            json={
                "name": "Максим",
                "email": email,
                "password": password,
            }
        )

        assert response.status_code == 201
        registered_user = response.json()

        required = await  client.post(
            "/auth/login",
            json={
                "email": email,
                "password":password,
            }
        )
        login_data = required.json()

        assert required.status_code == 200
        assert login_data["token_type"] == 'bearer'
        assert login_data["access_token"] != ''

        payload = jwt.decode(
            login_data["access_token"],
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]}
        )
        assert payload["sub"] == registered_user["id"]

    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(User).where(User.email == email)
        )
        await db_session.commit()

@pytest.mark.asyncio
async def test_authenticate_fail(client,db_session):
    email = f"{uuid4()}@example.com"
    password = "123456781"
    try:
        response = await client.post(
            "/auth/register",
            json={
                "name": "Максим",
                "email": email,
                "password": password,
            }
        )
        assert response.status_code == 201

        required = await  client.post(
            "/auth/login",
            json={
                "email": email,
                "password": "1234567812",
            }
        )
        login_data = required.json()

        assert required.status_code == 401
        assert required.json()["detail"] == "Неверный email или пароль"
        assert required.headers["WWW-Authenticate"] == "Bearer"
        assert "access_token" not in login_data

    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(User).where(User.email == email)
        )
        await db_session.commit()

@pytest.mark.asyncio
async def test_authenticate_fail_token(client):
    response = await client.get(
        "/auth/me"
    )
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.status_code == 401
    assert response.json()["detail"] == "Не удалось подтвердить авторизацию"

@pytest.mark.asyncio
async def test_me_returns_authenticated_user(client, db_session):
    email = f"{uuid4()}@example.com"
    password = "1234567812"

    try:
        registration_response = await client.post(
            "/auth/register",
            json={
                "name": "Максим",
                "email": email,
                "password": password,
            },
        )
        assert registration_response.status_code == 201
        registration_data = registration_response.json()

        login_response = await client.post(
            "/auth/login",
            json={
                "email": email,
                "password": password,
            },
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == registration_data["id"]
        assert data["email"] == email
        assert "password" not in data
        assert "password_hash" not in data

    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(User).where(User.email == email)
        )
        await db_session.commit()

@pytest.mark.asyncio
async def test_me_returns_authenticated_user_not_found(client):
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    wrong_key = secrets.token_hex(32)

    token = jwt.encode(
        {"sub": str(uuid4()), "exp": exp},
        wrong_key,
        algorithm=settings.jwt_algorithm)

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()['detail'] == "Не удалось подтвердить авторизацию"
@pytest.mark.asyncio
async def test_authenticate_rejects_missing_user(db_session):
    service = UserService(db_session)
    login_data = UserLogin(
        email=f"{uuid4()}@example.com",
        password="SomePassword123",
    )

    with pytest.raises(InvalidCredentialsError):
        await service.authenticate(login_data)

@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_user(db_session):
    user_id = uuid4()
    token = create_access_token(user_id)
    service = UserService(db_session)
    with pytest.raises(InvalidTokenError):
        await service.get_current_user(token)

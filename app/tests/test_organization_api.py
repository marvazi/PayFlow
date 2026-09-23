from app.models import User, Organization,Membership
from uuid import uuid4, UUID
import pytest
from sqlalchemy import delete, select
from app.models import User, Organization


@pytest.mark.asyncio
async def test_create_organization_with_owner(client,db_session):
    email = f"{uuid4()}@example.com"
    name = "asdd"
    password = "1234567890"
    organization_name = f"Test-{uuid4()}"
    try:
        response = await client.post(
            "/auth/register",
            json={
                "name": name,
                "email": email,
                "password": password,
            }
        )
        assert response.status_code == 201
        user_id = response.json()['id']


        required = await  client.post(
            "/auth/login",
            json={
                "email": email,
                "password":password,
            }
        )
        login_data = required.json()
        assert required.status_code == 200

        organizations = await client.post(
            "/organization",
            json={"name": organization_name},
            headers={"Authorization": f"Bearer {login_data['access_token']}"},
        )
        assert organizations.status_code == 201, organizations.text

        res = organizations.json()
        assert res["name"] == organization_name
        res = organizations.json()
        assert organizations.status_code == 201
        assert res['name'] == organization_name
        membership_result = await db_session.execute(
            select(Membership).where(
                Membership.organization_id == UUID(res["id"])
            )
        )
        membership = membership_result.scalar_one_or_none()
        assert membership
        assert str(membership.user_id) == user_id
        assert membership.role == "owner"


    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(Organization).where(Organization.name == organization_name)
        )
        await db_session.execute(
            delete(User).where(User.email == email)
        )
        await db_session.commit()

@pytest.mark.asyncio
async def test_create_organization_without_auth(client,db_session):
    name = f"Test-{uuid4()}"
    response = await client.post(
        "/organization",
        json={"name": name},
    )
    org = await db_session.execute(
        select(Organization).where(Organization.name == name)
    )
    org_res = org.scalar_one_or_none()
    assert org_res is None
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_users_see_only_their_organizations(client, db_session):
    organizations_url = "/organization"
    emails = [f"{uuid4()}@example.com" for _ in range(2)]
    organization_names = [f"Test-{uuid4()}" for _ in range(2)]
    password = "TestPassword123"

    tokens = []
    organization_ids = []

    try:
        for email, organization_name in zip(emails, organization_names):
            registration_response = await client.post(
                "/auth/register",
                json={
                    "name": "Тестовый пользователь",
                    "email": email,
                    "password": password,
                },
            )
            assert registration_response.status_code == 201, (
                registration_response.text
            )

            login_response = await client.post(
                "/auth/login",
                json={"email": email, "password": password},
            )
            assert login_response.status_code == 200, login_response.text

            token = login_response.json()["access_token"]
            tokens.append(token)

            organization_response = await client.post(
                organizations_url,
                json={"name": organization_name},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert organization_response.status_code == 201, (
                organization_response.text
            )
            organization_ids.append(organization_response.json()["id"])

        for token, expected_id in zip(tokens, organization_ids):
            response = await client.get(
                organizations_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200, response.text

            organizations = response.json()
            returned_ids = {item["id"] for item in organizations}

            assert returned_ids == {expected_id}
            assert len(organizations) == 1

    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(Organization).where(
                Organization.name.in_(organization_names)
            )
        )
        await db_session.execute(
            delete(User).where(User.email.in_(emails))
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_organization(client, db_session):
    organizations_url = "/organization"
    emails = [f"{uuid4()}@example.com" for _ in range(2)]
    names = [f"Test-{uuid4()}" for _ in range(2)]
    password = "TestPassword123"

    tokens = []
    organization_ids = []

    try:
        for email, name in zip(emails, names):
            registration = await client.post(
                "/auth/register",
                json={
                    "name": "Максим",
                    "email": email,
                    "password": password,
                },
            )
            assert registration.status_code == 201, registration.text

            login = await client.post(
                "/auth/login",
                json={"email": email, "password": password},
            )
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]
            tokens.append(token)

            creation = await client.post(
                organizations_url,
                json={"name": name},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert creation.status_code == 201, creation.text
            organization_ids.append(creation.json()["id"])

        target_url = f"{organizations_url}/{organization_ids[0]}"

        owner_response = await client.get(
            target_url,
            headers={"Authorization": f"Bearer {tokens[0]}"},
        )
        assert owner_response.status_code == 200, owner_response.text
        assert owner_response.json()["id"] == organization_ids[0]

        other_user_response = await client.get(
            target_url,
            headers={"Authorization": f"Bearer {tokens[1]}"},
        )
        assert other_user_response.status_code == 404, other_user_response.text
        assert other_user_response.json()["detail"] == "Организация не найдена"

    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(Organization).where(Organization.name.in_(names))
        )
        await db_session.execute(
            delete(User).where(User.email.in_(emails))
        )
        await db_session.commit()

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from app.models import Membership, Organization, User


@pytest.mark.asyncio
async def test_manager_cannot_add_member_via_api(client, db_session):
    organizations_url = "/organization"
    emails = [f"{uuid4()}@example.com" for _ in range(3)]
    organization_name = f"Test-{uuid4()}"
    password = "TestPassword123"
    user_ids = []

    try:
        # Регистрируем владельца, менеджера и будущего участника.
        for email in emails:
            response = await client.post(
                "/auth/register",
                json={
                    "name": "Тестовый пользователь",
                    "email": email,
                    "password": password,
                },
            )
            assert response.status_code == 201, response.text
            user_ids.append(response.json()["id"])

        # Получаем токены владельца и менеджера.
        tokens = []
        for email in emails[:2]:
            response = await client.post(
                "/auth/login",
                json={"email": email, "password": password},
            )
            assert response.status_code == 200, response.text
            tokens.append(response.json()["access_token"])

        owner_headers = {"Authorization": f"Bearer {tokens[0]}"}
        manager_headers = {"Authorization": f"Bearer {tokens[1]}"}

        # Владелец создаёт организацию.
        response = await client.post(
            organizations_url,
            json={"name": organization_name},
            headers=owner_headers,
        )
        assert response.status_code == 201, response.text
        organization_id = response.json()["id"]
        members_url = f"{organizations_url}/{organization_id}/members"

        # Владелец назначает второго пользователя менеджером.
        response = await client.post(
            members_url,
            json={"user_id": user_ids[1], "role": "manager"},
            headers=owner_headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["role"] == "manager"
        assert response.json()["user_id"] == user_ids[1]

        # Менеджер пытается добавить третьего пользователя.
        response = await client.post(
            members_url,
            json={"user_id": user_ids[2], "role": "viewer"},
            headers=manager_headers,
        )
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "Недостаточно прав"

        # После отказа участие не должно появиться.
        result = await db_session.execute(
            select(Membership).where(
                Membership.organization_id == UUID(organization_id),
                Membership.user_id == UUID(user_ids[2]),
            )
        )
        assert result.scalar_one_or_none() is None

    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(Organization).where(
                Organization.name == organization_name
            )
        )
        await db_session.execute(
            delete(User).where(User.email.in_(emails))
        )
        await db_session.commit()

    
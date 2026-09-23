from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from app.core.security import create_access_token
from app.models import Membership, Organization, User


@pytest_asyncio.fixture
async def membership_data(db_session):
    organization_id = uuid4()
    other_organization_id = uuid4()

    user_ids = {
        "owner": uuid4(),
        "manager": uuid4(),
        "viewer": uuid4(),
        "outsider": uuid4(),
    }

    expected_members = {
        str(user_ids["owner"]): "owner",
        str(user_ids["manager"]): "manager",
        str(user_ids["viewer"]): "viewer",
    }

    try:
        db_session.add_all([
            User(
                id=user_id,
                name=role,
                email=f"{user_id}@example.com",
                password_hash=None,
            )
            for role, user_id in user_ids.items()
        ])

        db_session.add_all([
            Organization(
                id=organization_id,
                name=f"Test-{organization_id}",
            ),
            Organization(
                id=other_organization_id,
                name=f"Test-{other_organization_id}",
            ),
        ])

        await db_session.flush()

        db_session.add_all([
            Membership(
                user_id=user_ids[role],
                organization_id=organization_id,
                role=role,
            )
            for role in ("owner", "manager", "viewer")
        ])

        # Посторонний пользователь владеет другой организацией.
        db_session.add(
            Membership(
                user_id=user_ids["outsider"],
                organization_id=other_organization_id,
                role="owner",
            )
        )

        # Авторизация использует отдельную сессию,
        # поэтому подготовленные данные нужно сохранить.
        await db_session.commit()

        yield {
            "organization_id": organization_id,
            "user_ids": user_ids,
            "expected_members": expected_members,
        }

    finally:
        await db_session.rollback()

        # Связанные Membership удаляются через ON DELETE CASCADE.
        await db_session.execute(
            delete(Organization).where(
                Organization.id.in_([
                    organization_id,
                    other_organization_id,
                ])
            )
        )

        await db_session.execute(
            delete(User).where(
                User.id.in_(list(user_ids.values()))
            )
        )

        await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager", "viewer"])
async def test_member_can_list_organization_members(
    client,
    membership_data,
    role,
):
    organization_id = membership_data["organization_id"]
    user_id = membership_data["user_ids"][role]
    token = create_access_token(user_id)

    response = await client.get(
        f"/organization/{organization_id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text

    members = response.json()

    assert len(members) == 3

    actual_members = {
        member["user_id"]: member["role"]
        for member in members
    }
    assert actual_members == membership_data["expected_members"]

    assert all(
        member["organization_id"] == str(organization_id)
        for member in members
    )

    # Участие из другой организации не должно попасть в ответ.
    outsider_id = str(membership_data["user_ids"]["outsider"])
    assert outsider_id not in actual_members


@pytest.mark.asyncio
async def test_outsider_cannot_list_members(client, membership_data):
    organization_id = membership_data["organization_id"]
    outsider_id = membership_data["user_ids"]["outsider"]
    token = create_access_token(outsider_id)

    response = await client.get(
        f"/organization/{organization_id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Организация не найдена"


@pytest.mark.asyncio
async def test_list_members_of_missing_organization(
    client,
    membership_data,
):
    owner_id = membership_data["user_ids"]["owner"]
    token = create_access_token(owner_id)

    response = await client.get(
        f"/organization/{uuid4()}/members",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Организация не найдена"


@pytest.mark.asyncio
async def test_list_members_requires_authentication(
    client,
    membership_data,
):
    organization_id = membership_data["organization_id"]

    response = await client.get(
        f"/organization/{organization_id}/members",
    )

    assert response.status_code == 401, response.text
    assert response.headers["WWW-Authenticate"] == "Bearer"

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target_role", "new_role"),
    [
        ("manager", "viewer"),
        ("viewer", "manager"),
        ("manager", "manager"),
    ],
)
async def test_owner_can_change_member_role(
    client, db_session, membership_data, target_role, new_role,
):
    organization_id = membership_data["organization_id"]
    owner_id = membership_data["user_ids"]["owner"]
    target_id = membership_data["user_ids"][target_role]
    token = create_access_token(owner_id)

    response = await client.patch(
        f"/organization/{organization_id}/members/{target_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": new_role},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user_id"] == str(target_id)
    assert data["organization_id"] == str(organization_id)
    assert data["role"] == new_role

    # Завершаем текущую транзакцию перед проверкой сохранённых данных.
    await db_session.rollback()

    saved_role = await db_session.scalar(
        select(Membership.role).where(
            Membership.user_id == target_id,
            Membership.organization_id == organization_id,
        )
    )
    assert saved_role == new_role


@pytest.mark.asyncio
@pytest.mark.parametrize("actor_role", ["manager", "viewer", "outsider"])
async def test_non_owner_cannot_change_member_role(
    client, db_session, membership_data, actor_role,
):
    organization_id = membership_data["organization_id"]
    actor_id = membership_data["user_ids"][actor_role]
    target_id = membership_data["user_ids"]["manager"]
    token = create_access_token(actor_id)

    response = await client.patch(
        f"/organization/{organization_id}/members/{target_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "viewer"},
    )

    expected_status = 404 if actor_role == "outsider" else 403
    assert response.status_code == expected_status, response.text

    await db_session.rollback()
    saved_role = await db_session.scalar(
        select(Membership.role).where(
            Membership.user_id == target_id,
            Membership.organization_id == organization_id,
        )
    )
    assert saved_role == "manager"


@pytest.mark.asyncio
async def test_owner_role_cannot_be_changed(
    client, db_session, membership_data,
):
    organization_id = membership_data["organization_id"]
    owner_id = membership_data["user_ids"]["owner"]
    token = create_access_token(owner_id)

    response = await client.patch(
        f"/organization/{organization_id}/members/{owner_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "viewer"},
    )

    assert response.status_code == 403, response.text

    await db_session.rollback()
    saved_role = await db_session.scalar(
        select(Membership.role).where(
            Membership.user_id == owner_id,
            Membership.organization_id == organization_id,
        )
    )
    assert saved_role == "owner"


@pytest.mark.asyncio
async def test_cannot_change_member_from_another_organization(
    client, db_session, membership_data,
):
    organization_id = membership_data["organization_id"]
    owner_id = membership_data["user_ids"]["owner"]
    outsider_id = membership_data["user_ids"]["outsider"]
    token = create_access_token(owner_id)

    response = await client.patch(
        f"/organization/{organization_id}/members/{outsider_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "viewer"},
    )

    assert response.status_code == 404, response.text

    await db_session.rollback()
    result = await db_session.execute(
        select(Membership.organization_id, Membership.role).where(
            Membership.user_id == outsider_id,
        )
    )
    memberships = result.all()

    # У постороннего осталось единственное участие в другой организации.
    assert len(memberships) == 1
    assert memberships[0].organization_id != organization_id
    assert memberships[0].role == "owner"


@pytest.mark.asyncio
async def test_change_role_for_missing_member(client, membership_data):
    organization_id = membership_data["organization_id"]
    owner_id = membership_data["user_ids"]["owner"]
    token = create_access_token(owner_id)

    response = await client.patch(
        f"/organization/{organization_id}/members/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "viewer"},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Участник не найден"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_role", ["owner", "admin"])
async def test_change_role_rejects_invalid_role(
    client, db_session, membership_data, invalid_role,
):
    organization_id = membership_data["organization_id"]
    owner_id = membership_data["user_ids"]["owner"]
    target_id = membership_data["user_ids"]["manager"]
    token = create_access_token(owner_id)

    response = await client.patch(
        f"/organization/{organization_id}/members/{target_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": invalid_role},
    )

    assert response.status_code == 422, response.text

    await db_session.rollback()
    saved_role = await db_session.scalar(
        select(Membership.role).where(
            Membership.user_id == target_id,
            Membership.organization_id == organization_id,
        )
    )
    assert saved_role == "manager"


@pytest.mark.asyncio
async def test_change_role_requires_authentication(
    client, db_session, membership_data,
):
    organization_id = membership_data["organization_id"]
    target_id = membership_data["user_ids"]["manager"]

    response = await client.patch(
        f"/organization/{organization_id}/members/{target_id}",
        json={"role": "viewer"},
    )

    assert response.status_code == 401, response.text
    assert response.headers["WWW-Authenticate"] == "Bearer"

    await db_session.rollback()
    saved_role = await db_session.scalar(
        select(Membership.role).where(
            Membership.user_id == target_id,
            Membership.organization_id == organization_id,
        )
    )
    assert saved_role == "manager"

@pytest.mark.asyncio
async def test_owner_can_remove_member(
    client, db_session, membership_data,
):
    organization_id = membership_data["organization_id"]
    owner_id = membership_data["user_ids"]["owner"]
    target_id = membership_data["user_ids"]["manager"]
    outsider_id = membership_data["user_ids"]["outsider"]

    # Добавляем удаляемого сотрудника ещё в одну организацию,
    # чтобы проверить сохранение другого участия.
    other_organization_id = await db_session.scalar(
        select(Membership.organization_id).where(
            Membership.user_id == outsider_id,
        )
    )
    assert other_organization_id is not None

    db_session.add(
        Membership(
            user_id=target_id,
            organization_id=other_organization_id,
            role="viewer",
        )
    )
    await db_session.commit()

    token = create_access_token(owner_id)
    response = await client.delete(
        f"/organization/{organization_id}/members/{target_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204, response.text
    assert response.content == b""

    await db_session.rollback()

    deleted_membership = await db_session.scalar(
        select(Membership.id).where(
            Membership.user_id == target_id,
            Membership.organization_id == organization_id,
        )
    )
    assert deleted_membership is None

    # Учётная запись пользователя сохранилась.
    saved_user_id = await db_session.scalar(
        select(User.id).where(User.id == target_id)
    )
    assert saved_user_id == target_id

    # Его участие в другой организации тоже сохранилось.
    other_role = await db_session.scalar(
        select(Membership.role).where(
            Membership.user_id == target_id,
            Membership.organization_id == other_organization_id,
        )
    )
    assert other_role == "viewer"

    # Освобождаем сессию перед следующими HTTP-запросами.
    await db_session.rollback()

    # Старый токен больше не даёт доступ к прежней организации.
    former_member_token = create_access_token(target_id)
    headers = {"Authorization": f"Bearer {former_member_token}"}

    organization_response = await client.get(
        f"/organization/{organization_id}",
        headers=headers,
    )
    assert organization_response.status_code == 404

    members_response = await client.get(
        f"/organization/{organization_id}/members",
        headers=headers,
    )
    assert members_response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("actor_role", ["manager", "viewer", "outsider"])
async def test_non_owner_cannot_remove_member(
    client, db_session, membership_data, actor_role,
):
    organization_id = membership_data["organization_id"]
    actor_id = membership_data["user_ids"][actor_role]

    # Для manager и viewer выбираем другого сотрудника.
    target_role = "manager" if actor_role == "viewer" else "viewer"
    target_id = membership_data["user_ids"][target_role]
    token = create_access_token(actor_id)

    response = await client.delete(
        f"/organization/{organization_id}/members/{target_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    expected_status = 404 if actor_role == "outsider" else 403
    assert response.status_code == expected_status, response.text

    await db_session.rollback()

    saved_role = await db_session.scalar(
        select(Membership.role).where(
            Membership.user_id == target_id,
            Membership.organization_id == organization_id,
        )
    )
    assert saved_role == target_role


@pytest.mark.asyncio
async def test_owner_cannot_remove_self(
    client, db_session, membership_data,
):
    organization_id = membership_data["organization_id"]
    owner_id = membership_data["user_ids"]["owner"]
    token = create_access_token(owner_id)

    response = await client.delete(
        f"/organization/{organization_id}/members/{owner_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, response.text

    await db_session.rollback()

    saved_role = await db_session.scalar(
        select(Membership.role).where(
            Membership.user_id == owner_id,
            Membership.organization_id == organization_id,
        )
    )
    assert saved_role == "owner"


@pytest.mark.asyncio
async def test_remove_missing_member(client, membership_data):
    organization_id = membership_data["organization_id"]
    owner_id = membership_data["user_ids"]["owner"]
    token = create_access_token(owner_id)

    response = await client.delete(
        f"/organization/{organization_id}/members/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Участник не найден"


@pytest.mark.asyncio
async def test_cannot_remove_member_from_another_organization(
    client, db_session, membership_data,
):
    organization_id = membership_data["organization_id"]
    owner_id = membership_data["user_ids"]["owner"]
    outsider_id = membership_data["user_ids"]["outsider"]

    # Запоминаем конкретное чужое участие до запроса.
    before_result = await db_session.execute(
        select(
            Membership.id,
            Membership.organization_id,
            Membership.role,
        ).where(Membership.user_id == outsider_id)
    )
    before = before_result.one()
    await db_session.rollback()

    token = create_access_token(owner_id)
    response = await client.delete(
        f"/organization/{organization_id}/members/{outsider_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404, response.text

    await db_session.rollback()

    after_result = await db_session.execute(
        select(
            Membership.id,
            Membership.organization_id,
            Membership.role,
        ).where(Membership.user_id == outsider_id)
    )
    after = after_result.one()

    assert tuple(after) == tuple(before)


@pytest.mark.asyncio
async def test_remove_member_requires_authentication(
    client, db_session, membership_data,
):
    organization_id = membership_data["organization_id"]
    target_id = membership_data["user_ids"]["manager"]

    response = await client.delete(
        f"/organization/{organization_id}/members/{target_id}",
    )

    assert response.status_code == 401, response.text
    assert response.headers["WWW-Authenticate"] == "Bearer"

    await db_session.rollback()

    saved_membership_id = await db_session.scalar(
        select(Membership.id).where(
            Membership.user_id == target_id,
            Membership.organization_id == organization_id,
        )
    )
    assert saved_membership_id is not None
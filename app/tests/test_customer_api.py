from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app.core.security import create_access_token
from app.models import Customer, Membership, Organization, User


@pytest_asyncio.fixture
async def customer_data(db_session):
    organization_ids = [uuid4(), uuid4()]
    user_ids = {
        role: uuid4()
        for role in ("owner", "manager", "viewer", "outsider")
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
            )
            for organization_id in organization_ids
        ])
        await db_session.flush()

        db_session.add_all([
            Membership(
                user_id=user_ids[role],
                organization_id=organization_ids[0],
                role=role,
            )
            for role in ("owner", "manager", "viewer")
        ])

        # Тот же владелец управляет второй организацией.
        db_session.add(
            Membership(
                user_id=user_ids["owner"],
                organization_id=organization_ids[1],
                role="owner",
            )
        )
        await db_session.commit()

        yield {
            "organization_ids": organization_ids,
            "user_ids": user_ids,
        }

    finally:
        await db_session.rollback()

        # У Customer стоит ON DELETE RESTRICT:
        # клиентов удаляем раньше организаций.
        await db_session.execute(
            delete(Customer).where(
                Customer.organization_id.in_(organization_ids)
            )
        )
        await db_session.execute(
            delete(Organization).where(
                Organization.id.in_(organization_ids)
            )
        )
        await db_session.execute(
            delete(User).where(
                User.id.in_(list(user_ids.values()))
            )
        )
        await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager"])
async def test_owner_and_manager_can_create_customer(
    client, db_session, customer_data, role,
):
    organization_id = customer_data["organization_ids"][0]
    token = create_access_token(customer_data["user_ids"][role])
    email = f"customer-{uuid4()}@example.com"

    response = await client.post(
        f"/organization/{organization_id}/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": " Максим ",
            "email": f" {email.upper()} ",
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["name"] == "Максим"
    assert data["email"] == email
    assert data["organization_id"] == str(organization_id)
    assert data["id"]
    assert data["created_at"]
    assert "password_hash" not in data

    await db_session.rollback()

    result = await db_session.execute(
        select(Customer).where(
            Customer.organization_id == organization_id,
            Customer.email == email,
        )
    )
    saved_customer = result.scalar_one()

    assert str(saved_customer.id) == data["id"]
    assert saved_customer.name == "Максим"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "expected_status"),
    [("viewer", 403), ("outsider", 404)],
)
async def test_customer_creation_requires_access(
    client, db_session, customer_data, role, expected_status,
):
    organization_id = customer_data["organization_ids"][0]
    token = create_access_token(customer_data["user_ids"][role])

    response = await client.post(
        f"/organization/{organization_id}/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Максим",
            "email": f"{uuid4()}@example.com",
        },
    )

    assert response.status_code == expected_status, response.text

    await db_session.rollback()
    count = await db_session.scalar(
        select(func.count()).select_from(Customer).where(
            Customer.organization_id == organization_id,
        )
    )
    assert count == 0


@pytest.mark.asyncio
async def test_customer_creation_rejects_duplicate_email(
    client, db_session, customer_data,
):
    organization_id = customer_data["organization_ids"][0]
    token = create_access_token(customer_data["user_ids"]["owner"])
    headers = {"Authorization": f"Bearer {token}"}
    email = f"customer-{uuid4()}@example.com"
    url = f"/organization/{organization_id}/customers"

    first_response = await client.post(
        url,
        headers=headers,
        json={"name": "Первый клиент", "email": email},
    )
    assert first_response.status_code == 201, first_response.text

    second_response = await client.post(
        url,
        headers=headers,
        json={
            "name": "Второй клиент",
            "email": f" {email.upper()} ",
        },
    )

    assert second_response.status_code == 409, second_response.text
    assert second_response.json()["detail"] == (
        "Клиент с таким email уже существует в организации"
    )

    await db_session.rollback()

    result = await db_session.execute(
        select(Customer).where(
            Customer.organization_id == organization_id,
            Customer.email == email,
        )
    )
    customers = result.scalars().all()

    assert len(customers) == 1
    assert customers[0].name == "Первый клиент"


@pytest.mark.asyncio
async def test_same_customer_email_allowed_in_different_organizations(
    client, db_session, customer_data,
):
    organization_ids = customer_data["organization_ids"]
    token = create_access_token(customer_data["user_ids"]["owner"])
    email = f"customer-{uuid4()}@example.com"
    created_ids = []

    for organization_id in organization_ids:
        response = await client.post(
            f"/organization/{organization_id}/customers",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Максим", "email": email},
        )

        assert response.status_code == 201, response.text
        assert response.json()["organization_id"] == str(organization_id)
        created_ids.append(response.json()["id"])

    assert len(set(created_ids)) == 2

    await db_session.rollback()

    result = await db_session.execute(
        select(Customer.organization_id).where(
            Customer.email == email,
            Customer.organization_id.in_(organization_ids),
        )
    )
    assert set(result.scalars().all()) == set(organization_ids)


@pytest.mark.asyncio
async def test_customer_creation_requires_authentication(
    client, db_session, customer_data,
):
    organization_id = customer_data["organization_ids"][0]

    response = await client.post(
        f"/organization/{organization_id}/customers",
        json={
            "name": "Максим",
            "email": f"{uuid4()}@example.com",
        },
    )

    assert response.status_code == 401, response.text
    assert response.headers["WWW-Authenticate"] == "Bearer"

    await db_session.rollback()
    count = await db_session.scalar(
        select(func.count()).select_from(Customer).where(
            Customer.organization_id == organization_id,
        )
    )
    assert count == 0


@pytest.mark.asyncio
async def test_customer_creation_in_missing_organization(
    client, customer_data,
):
    token = create_access_token(customer_data["user_ids"]["owner"])

    response = await client.post(
        f"/organization/{uuid4()}/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Максим",
            "email": f"{uuid4()}@example.com",
        },
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Организация не найдена"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_data",
    [
        {"name": "   ", "email": "customer@example.com"},
        {"name": "А" * 256, "email": "customer@example.com"},
        {"name": "Максим", "email": "not-an-email"},
        {"email": "customer@example.com"},
        {"name": "Максим"},
    ],
    ids=[
        "blank-name",
        "long-name",
        "invalid-email",
        "missing-name",
        "missing-email",
    ],
)
async def test_customer_creation_rejects_invalid_data(
    client, db_session, customer_data, invalid_data,
):
    organization_id = customer_data["organization_ids"][0]
    token = create_access_token(customer_data["user_ids"]["owner"])

    response = await client.post(
        f"/organization/{organization_id}/customers",
        headers={"Authorization": f"Bearer {token}"},
        json=invalid_data,
    )

    assert response.status_code == 422, response.text

    await db_session.rollback()
    count = await db_session.scalar(
        select(func.count()).select_from(Customer).where(
            Customer.organization_id == organization_id,
        )
    )
    assert count == 0

@pytest_asyncio.fixture
async def customers_for_read(db_session, customer_data):
    organization_id, other_organization_id = (
        customer_data["organization_ids"]
    )
    customer_id = uuid4()
    other_customer_id = uuid4()
    email = f"{uuid4()}@example.com"

    db_session.add_all([
        Customer(
            id=customer_id,
            organization_id=organization_id,
            name="Первый клиент",
            email=email,
        ),
        Customer(
            id=other_customer_id,
            organization_id=other_organization_id,
            name="Клиент другой организации",
            email=f"{uuid4()}@example.com",
        ),
    ])
    await db_session.commit()

    return {
        **customer_data,
        "customer_id": customer_id,
        "other_customer_id": other_customer_id,
        "customer_email": email,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager", "viewer"])
async def test_member_can_list_customers(
    client, customers_for_read, role,
):
    organization_id = customers_for_read["organization_ids"][0]
    token = create_access_token(customers_for_read["user_ids"][role])

    response = await client.get(
        f"/organization/{organization_id}/customers",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    customers = response.json()

    # В ответе только клиент запрошенной организации.
    assert len(customers) == 1
    assert customers[0]["id"] == str(customers_for_read["customer_id"])
    assert customers[0]["organization_id"] == str(organization_id)
    assert customers[0]["name"] == "Первый клиент"
    assert customers[0]["email"] == customers_for_read["customer_email"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager", "viewer"])
async def test_member_can_get_customer(
    client, customers_for_read, role,
):
    organization_id = customers_for_read["organization_ids"][0]
    customer_id = customers_for_read["customer_id"]
    token = create_access_token(customers_for_read["user_ids"][role])

    response = await client.get(
        f"/organization/{organization_id}/customers/{customer_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    customer = response.json()

    assert customer["id"] == str(customer_id)
    assert customer["organization_id"] == str(organization_id)
    assert customer["name"] == "Первый клиент"
    assert customer["email"] == customers_for_read["customer_email"]
    assert customer["created_at"]


@pytest.mark.asyncio
async def test_organization_without_customers_returns_empty_list(
    client, customer_data,
):
    organization_id = customer_data["organization_ids"][0]
    token = create_access_token(customer_data["user_ids"]["owner"])

    response = await client.get(
        f"/organization/{organization_id}/customers",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("get_single", [False, True], ids=["list", "get"])
async def test_outsider_cannot_read_customers(
    client, customers_for_read, get_single,
):
    organization_id = customers_for_read["organization_ids"][0]
    token = create_access_token(
        customers_for_read["user_ids"]["outsider"]
    )
    url = f"/organization/{organization_id}/customers"

    if get_single:
        url += f"/{customers_for_read['customer_id']}"

    response = await client.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Организация не найдена"


@pytest.mark.asyncio
async def test_customer_id_is_scoped_to_organization(
    client, customers_for_read,
):
    organization_id = customers_for_read["organization_ids"][0]
    other_customer_id = customers_for_read["other_customer_id"]

    # Владелец состоит в обеих организациях.
    # Но клиент второй не должен находиться по пути первой.
    token = create_access_token(customers_for_read["user_ids"]["owner"])

    response = await client.get(
        f"/organization/{organization_id}/customers/{other_customer_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Клиент не найден"


@pytest.mark.asyncio
async def test_get_missing_customer(client, customer_data):
    organization_id = customer_data["organization_ids"][0]
    token = create_access_token(customer_data["user_ids"]["owner"])

    response = await client.get(
        f"/organization/{organization_id}/customers/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Клиент не найден"


@pytest.mark.asyncio
@pytest.mark.parametrize("get_single", [False, True], ids=["list", "get"])
async def test_read_customers_of_missing_organization(
    client, customer_data, get_single,
):
    token = create_access_token(customer_data["user_ids"]["owner"])
    url = f"/organization/{uuid4()}/customers"

    if get_single:
        url += f"/{uuid4()}"

    response = await client.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Организация не найдена"


@pytest.mark.asyncio
@pytest.mark.parametrize("get_single", [False, True], ids=["list", "get"])
async def test_read_customers_requires_authentication(
    client, customers_for_read, get_single,
):
    organization_id = customers_for_read["organization_ids"][0]
    url = f"/organization/{organization_id}/customers"

    if get_single:
        url += f"/{customers_for_read['customer_id']}"

    response = await client.get(url)

    assert response.status_code == 401, response.text
    assert response.headers["WWW-Authenticate"] == "Bearer"
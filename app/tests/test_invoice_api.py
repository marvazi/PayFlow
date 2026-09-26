from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.models import Customer, Membership, Organization, User
from app.models.invoice import Invoice


@pytest_asyncio.fixture
async def invoice_data(db_session):
    organization_id = uuid4()
    other_organization_id = uuid4()
    customer_id = uuid4()
    other_customer_id = uuid4()
    invoice_id = uuid4()
    other_invoice_id = uuid4()

    user_ids = {
        role: uuid4()
        for role in ("owner", "manager", "viewer", "outsider")
    }
    organization_ids = [organization_id, other_organization_id]

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
            Organization(id=org_id, name=f"Test-{org_id}")
            for org_id in organization_ids
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
        db_session.add(
            Membership(
                user_id=user_ids["outsider"],
                organization_id=other_organization_id,
                role="owner",
            )
        )

        db_session.add_all([
            Customer(
                id=customer_id,
                organization_id=organization_id,
                name="Первый клиент",
                email=f"{customer_id}@example.com",
            ),
            Customer(
                id=other_customer_id,
                organization_id=other_organization_id,
                name="Чужой клиент",
                email=f"{other_customer_id}@example.com",
            ),
        ])
        await db_session.flush()

        db_session.add_all([
            Invoice(
                id=invoice_id,
                organization_id=organization_id,
                customer_id=customer_id,
                description="Первый счёт",
                amount_minor=10000,
                currency="RUB",
                status="draft",
            ),
            Invoice(
                id=other_invoice_id,
                organization_id=other_organization_id,
                customer_id=other_customer_id,
                description="Чужой счёт",
                amount_minor=20000,
                currency="RUB",
                status="draft",
            ),
        ])
        await db_session.commit()

        yield {
            "organization_id": organization_id,
            "customer_id": customer_id,
            "other_customer_id": other_customer_id,
            "invoice_id": invoice_id,
            "other_invoice_id": other_invoice_id,
            "headers": {
                role: {
                    "Authorization": (
                        f"Bearer {create_access_token(user_id)}"
                    )
                }
                for role, user_id in user_ids.items()
            },
        }
    finally:
        await db_session.rollback()

        # Порядок важен: внешние ключи счетов используют RESTRICT.
        await db_session.execute(
            delete(Invoice).where(
                Invoice.organization_id.in_(organization_ids)
            )
        )
        await db_session.execute(
            delete(Customer).where(
                Customer.organization_id.in_(organization_ids)
            )
        )
        await db_session.execute(
            delete(Membership).where(
                Membership.organization_id.in_(organization_ids)
            )
        )
        await db_session.execute(
            delete(Organization).where(
                Organization.id.in_(organization_ids)
            )
        )
        await db_session.execute(
            delete(User).where(User.id.in_(list(user_ids.values())))
        )
        await db_session.commit()


def invoices_url(data):
    return f"/organization/{data['organization_id']}/invoices"


def invoice_payload(data):
    return {
        "customer_id": str(data["customer_id"]),
        "description": "  Оплата разработки  ",
        "amount_minor": 150050,
        "currency": "RUB",
    }


async def invoice_ids_in_db(db_session, organization_id):
    # Закрываем транзакцию чтения до следующего HTTP-запроса.
    await db_session.rollback()
    try:
        result = await db_session.execute(
            select(Invoice.id).where(
                Invoice.organization_id == organization_id
            )
        )
        return set(result.scalars().all())
    finally:
        await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager"])
async def test_create_invoice(client, db_session, invoice_data, role):
    response = await client.post(
        invoices_url(invoice_data),
        headers=invoice_data["headers"][role],
        json=invoice_payload(invoice_data),
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["customer_id"] == str(invoice_data["customer_id"])
    assert data["organization_id"] == str(invoice_data["organization_id"])
    assert data["description"] == "Оплата разработки"
    assert data["amount_minor"] == 150050
    assert data["currency"] == "RUB"
    assert data["status"] == "draft"
    assert data["created_at"]

    await db_session.rollback()
    try:
        result = await db_session.execute(
            select(
                Invoice.customer_id,
                Invoice.organization_id,
                Invoice.description,
                Invoice.amount_minor,
                Invoice.currency,
                Invoice.status,
            ).where(Invoice.id == UUID(data["id"]))
        )
        saved = result.mappings().one()

        assert saved["customer_id"] == invoice_data["customer_id"]
        assert saved["organization_id"] == invoice_data["organization_id"]
        assert saved["description"] == "Оплата разработки"
        assert saved["amount_minor"] == 150050
        assert saved["currency"] == "RUB"
        assert saved["status"] == "draft"
    finally:
        await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "expected_status"),
    [("viewer", 403), ("outsider", 404)],
)
async def test_create_invoice_forbidden(
    client, db_session, invoice_data, role, expected_status
):
    before = await invoice_ids_in_db(
        db_session, invoice_data["organization_id"]
    )

    response = await client.post(
        invoices_url(invoice_data),
        headers=invoice_data["headers"][role],
        json=invoice_payload(invoice_data),
    )

    assert response.status_code == expected_status, response.text
    assert await invoice_ids_in_db(
        db_session, invoice_data["organization_id"]
    ) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("customer_kind", ["missing", "other_organization"])
async def test_create_invoice_rejects_wrong_customer(
    client, db_session, invoice_data, customer_kind
):
    payload = invoice_payload(invoice_data)
    payload["customer_id"] = str(
        uuid4()
        if customer_kind == "missing"
        else invoice_data["other_customer_id"]
    )
    before = await invoice_ids_in_db(
        db_session, invoice_data["organization_id"]
    )

    response = await client.post(
        invoices_url(invoice_data),
        headers=invoice_data["headers"]["owner"],
        json=payload,
    )

    assert response.status_code == 404, response.text
    assert await invoice_ids_in_db(
        db_session, invoice_data["organization_id"]
    ) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount_minor", 0),
        ("amount_minor", -1),
        ("amount_minor", 1.5),
        ("amount_minor", "100"),
        ("amount_minor", True),
        ("amount_minor", None),
        ("description", ""),
        ("description", "   "),
        ("description", "x" * 501),
        ("description", None),
        ("currency", "USD"),
        ("customer_id", "not-a-uuid"),
    ],
)
async def test_create_invoice_validation(
    client, db_session, invoice_data, field, value
):
    payload = invoice_payload(invoice_data)
    payload[field] = value
    before = await invoice_ids_in_db(
        db_session, invoice_data["organization_id"]
    )

    response = await client.post(
        invoices_url(invoice_data),
        headers=invoice_data["headers"]["owner"],
        json=payload,
    )

    assert response.status_code == 422, response.text
    assert await invoice_ids_in_db(
        db_session, invoice_data["organization_id"]
    ) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager", "viewer"])
async def test_list_invoices_is_scoped_to_organization(
    client, invoice_data, role
):
    response = await client.get(
        invoices_url(invoice_data),
        headers=invoice_data["headers"][role],
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert [item["id"] for item in data] == [
        str(invoice_data["invoice_id"])
    ]
    assert all(
        item["organization_id"] == str(invoice_data["organization_id"])
        for item in data
    )


@pytest.mark.asyncio
async def test_list_invoices_empty(client, db_session, invoice_data):
    await db_session.execute(
        delete(Invoice).where(
            Invoice.organization_id == invoice_data["organization_id"]
        )
    )
    await db_session.commit()

    response = await client.get(
        invoices_url(invoice_data),
        headers=invoice_data["headers"]["viewer"],
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager", "viewer"])
async def test_get_invoice(client, invoice_data, role):
    response = await client.get(
        f"{invoices_url(invoice_data)}/{invoice_data['invoice_id']}",
        headers=invoice_data["headers"][role],
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["id"] == str(invoice_data["invoice_id"])
    assert data["customer_id"] == str(invoice_data["customer_id"])
    assert data["organization_id"] == str(invoice_data["organization_id"])
    assert data["amount_minor"] == 10000
    assert data["status"] == "draft"


@pytest.mark.asyncio
@pytest.mark.parametrize("invoice_kind", ["missing", "other_organization"])
async def test_get_invoice_not_found(client, invoice_data, invoice_kind):
    invoice_id = (
        uuid4()
        if invoice_kind == "missing"
        else invoice_data["other_invoice_id"]
    )

    response = await client.get(
        f"{invoices_url(invoice_data)}/{invoice_id}",
        headers=invoice_data["headers"]["owner"],
    )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("detail", [False, True])
async def test_outsider_cannot_read_invoices(client, invoice_data, detail):
    url = invoices_url(invoice_data)
    if detail:
        url += f"/{invoice_data['invoice_id']}"

    response = await client.get(
        url,
        headers=invoice_data["headers"]["outsider"],
    )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["create", "list", "get"])
async def test_invoices_require_authentication(
    client, invoice_data, action
):
    url = invoices_url(invoice_data)

    if action == "create":
        response = await client.post(
            url, json=invoice_payload(invoice_data)
        )
    elif action == "get":
        response = await client.get(
            f"{url}/{invoice_data['invoice_id']}"
        )
    else:
        response = await client.get(url)

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager"])
async def test_cannot_delete_customer_with_invoice(
    client, db_session, invoice_data, role
):
    customer_url = (
        f"/organization/{invoice_data['organization_id']}"
        f"/customers/{invoice_data['customer_id']}"
    )

    response = await client.delete(
        customer_url,
        headers=invoice_data["headers"][role],
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == (
        "Нельзя удалить клиента, у которого есть счета"
    )

    # После отказа оба объекта должны оставаться доступны.
    customer_response = await client.get(
        customer_url,
        headers=invoice_data["headers"][role],
    )
    assert customer_response.status_code == 200, customer_response.text
    assert customer_response.json()["id"] == str(
        invoice_data["customer_id"]
    )

    invoice_response = await client.get(
        f"{invoices_url(invoice_data)}/{invoice_data['invoice_id']}",
        headers=invoice_data["headers"][role],
    )
    assert invoice_response.status_code == 200, invoice_response.text
    assert invoice_response.json()["customer_id"] == str(
        invoice_data["customer_id"]
    )

    # Проверяем сохранность записей непосредственно в БД.
    await db_session.rollback()
    try:
        customer_result = await db_session.execute(
            select(Customer.id).where(
                Customer.id == invoice_data["customer_id"]
            )
        )
        assert customer_result.scalar_one_or_none() is not None

        invoice_result = await db_session.execute(
            select(Invoice.id).where(
                Invoice.id == invoice_data["invoice_id"]
            )
        )
        assert invoice_result.scalar_one_or_none() is not None
    finally:
        await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager"])
async def test_delete_customer_without_invoices(
    client, db_session, invoice_data, role
):
    customer_id = uuid4()
    db_session.add(
        Customer(
            id=customer_id,
            organization_id=invoice_data["organization_id"],
            name="Клиент без счетов",
            email=f"{customer_id}@example.com",
        )
    )
    await db_session.commit()

    response = await client.delete(
        f"/organization/{invoice_data['organization_id']}"
        f"/customers/{customer_id}",
        headers=invoice_data["headers"][role],
    )

    assert response.status_code == 204, response.text
    assert response.content == b""

    await db_session.rollback()
    try:
        result = await db_session.execute(
            select(Customer.id).where(Customer.id == customer_id)
        )
        assert result.scalar_one_or_none() is None
    finally:
        await db_session.rollback()
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update

from app.core.security import create_access_token
from app.models import Customer, Membership, Organization, User
from app.models.invoice import Invoice
from app.models.payment import Payment


@pytest_asyncio.fixture
async def payment_data(db_session):
    organization_id = uuid4()
    other_organization_id = uuid4()
    organization_ids = [organization_id, other_organization_id]

    customer_id = uuid4()
    other_customer_id = uuid4()

    invoice_id = uuid4()
    empty_invoice_id = uuid4()
    other_invoice_id = uuid4()

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
            Organization(id=organization_id, name=f"Test-{uuid4()}"),
            Organization(id=other_organization_id, name=f"Test-{uuid4()}"),
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
                email=f"{uuid4()}@example.com",
            ),
            Customer(
                id=other_customer_id,
                organization_id=other_organization_id,
                name="Другой клиент",
                email=f"{uuid4()}@example.com",
            ),
        ])
        await db_session.flush()

        db_session.add_all([
            Invoice(
                id=invoice_id,
                organization_id=organization_id,
                customer_id=customer_id,
                description="Основной счёт",
                amount_minor=150050,
                currency="RUB",
                status="issued",
            ),
            Invoice(
                id=empty_invoice_id,
                organization_id=organization_id,
                customer_id=customer_id,
                description="Счёт без платежей",
                amount_minor=20000,
                currency="RUB",
                status="issued",
            ),
            Invoice(
                id=other_invoice_id,
                organization_id=other_organization_id,
                customer_id=other_customer_id,
                description="Счёт другой организации",
                amount_minor=30000,
                currency="RUB",
                status="issued",
            ),
        ])
        await db_session.commit()

        yield {
            "organization_id": organization_id,
            "other_organization_id": other_organization_id,
            "invoice_id": invoice_id,
            "empty_invoice_id": empty_invoice_id,
            "other_invoice_id": other_invoice_id,
            "headers": {
                role: {
                    "Authorization": f"Bearer {create_access_token(user_id)}"
                }
                for role, user_id in user_ids.items()
            },
        }

    finally:
        await db_session.rollback()

        # Сначала удаляем записи, которые ссылаются на другие таблицы.
        for model in (Payment, Invoice, Customer, Membership):
            await db_session.execute(
                delete(model).where(
                    model.organization_id.in_(organization_ids)
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


def payments_url(data, organization_id=None):
    if organization_id is None:
        organization_id = data["organization_id"]
    return f"/organization/{organization_id}/payments"


async def create_payment(client, data):
    response = await client.post(
        payments_url(data),
        headers=data["headers"]["owner"],
        json={"invoice_id": str(data["invoice_id"])},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def read_payments(db_session, organization_id):
    """Читаем значения из БД, не оставляя открытую транзакцию."""
    await db_session.rollback()
    try:
        result = await db_session.execute(
            select(
                Payment.id,
                Payment.organization_id,
                Payment.invoice_id,
                Payment.amount_minor,
                Payment.currency,
                Payment.status,
                Payment.created_at,
                Payment.updated_at,
            )
            .where(Payment.organization_id == organization_id)
            .order_by(Payment.created_at, Payment.id)
        )
        return [dict(row) for row in result.mappings().all()]
    finally:
        await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager"])
async def test_create_payment_success(client, db_session, payment_data, role):
    response = await client.post(
        payments_url(payment_data),
        headers=payment_data["headers"][role],
        json={"invoice_id": str(payment_data["invoice_id"])},
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["organization_id"] == str(payment_data["organization_id"])
    assert body["invoice_id"] == str(payment_data["invoice_id"])
    assert body["amount_minor"] == 150050
    assert body["currency"] == "RUB"
    assert body["status"] == "pending"
    assert body["created_at"]
    assert body["updated_at"]

    rows = await read_payments(
        db_session, payment_data["organization_id"]
    )
    assert len(rows) == 1
    assert rows[0]["id"] == UUID(body["id"])
    assert rows[0]["invoice_id"] == payment_data["invoice_id"]
    assert rows[0]["amount_minor"] == 150050
    assert rows[0]["currency"] == "RUB"
    assert rows[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_create_payment_rejects_duplicate_pending(
    client, db_session, payment_data
):
    await create_payment(client, payment_data)
    before = await read_payments(
        db_session, payment_data["organization_id"]
    )

    response = await client.post(
        payments_url(payment_data),
        headers=payment_data["headers"]["owner"],
        json={"invoice_id": str(payment_data["invoice_id"])},
    )

    assert response.status_code == 409, response.text
    assert await read_payments(
        db_session, payment_data["organization_id"]
    ) == before


@pytest.mark.asyncio
async def test_create_payment_after_failed_attempt(
    client, db_session, payment_data
):
    first = await create_payment(client, payment_data)

    # Имитируем завершённую неудачную попытку.
    await db_session.execute(
        update(Payment)
        .where(Payment.id == UUID(first["id"]))
        .values(status="failed")
    )
    await db_session.commit()

    second = await create_payment(client, payment_data)

    assert second["id"] != first["id"]
    assert second["status"] == "pending"

    rows = await read_payments(
        db_session, payment_data["organization_id"]
    )
    assert len(rows) == 2
    assert {row["status"] for row in rows} == {"failed", "pending"}


@pytest.mark.asyncio
@pytest.mark.parametrize("invoice_status", ["draft", "paid", "cancelled"])
async def test_create_payment_rejects_invoice_status(
    client, db_session, payment_data, invoice_status
):
    await db_session.execute(
        update(Invoice)
        .where(Invoice.id == payment_data["invoice_id"])
        .values(status=invoice_status)
    )
    await db_session.commit()

    response = await client.post(
        payments_url(payment_data),
        headers=payment_data["headers"]["owner"],
        json={"invoice_id": str(payment_data["invoice_id"])},
    )

    assert response.status_code == 409, response.text
    assert await read_payments(
        db_session, payment_data["organization_id"]
    ) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "expected_status"),
    [("viewer", 403), ("outsider", 404)],
)
async def test_create_payment_checks_permissions(
    client, db_session, payment_data, role, expected_status
):
    response = await client.post(
        payments_url(payment_data),
        headers=payment_data["headers"][role],
        json={"invoice_id": str(payment_data["invoice_id"])},
    )

    assert response.status_code == expected_status, response.text
    assert await read_payments(
        db_session, payment_data["organization_id"]
    ) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["missing", "other_organization"])
async def test_create_payment_rejects_unavailable_invoice(
    client, db_session, payment_data, target
):
    invoice_id = (
        uuid4()
        if target == "missing"
        else payment_data["other_invoice_id"]
    )

    response = await client.post(
        payments_url(payment_data),
        headers=payment_data["headers"]["owner"],
        json={"invoice_id": str(invoice_id)},
    )

    assert response.status_code == 404, response.text
    for organization_id in (
        payment_data["organization_id"],
        payment_data["other_organization_id"],
    ):
        assert await read_payments(db_session, organization_id) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra",
    [
        {"status": "succeeded"},
        {"amount_minor": 1},
        {"currency": "USD"},
        {"organization_id": str(uuid4())},
    ],
)
async def test_create_payment_rejects_extra_fields(
    client, db_session, payment_data, extra
):
    response = await client.post(
        payments_url(payment_data),
        headers=payment_data["headers"]["owner"],
        json={
            "invoice_id": str(payment_data["invoice_id"]),
            **extra,
        },
    )

    assert response.status_code == 422, response.text
    assert await read_payments(
        db_session, payment_data["organization_id"]
    ) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [{}, {"invoice_id": None}, {"invoice_id": "not-a-uuid"}],
)
async def test_create_payment_validates_invoice_id(
    client, db_session, payment_data, payload
):
    response = await client.post(
        payments_url(payment_data),
        headers=payment_data["headers"]["owner"],
        json=payload,
    )

    assert response.status_code == 422, response.text
    assert await read_payments(
        db_session, payment_data["organization_id"]
    ) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager", "viewer"])
async def test_get_payment_success(client, payment_data, role):
    created = await create_payment(client, payment_data)

    response = await client.get(
        f"{payments_url(payment_data)}/{created['id']}",
        headers=payment_data["headers"][role],
    )

    assert response.status_code == 200, response.text
    assert response.json() == created


@pytest.mark.asyncio
async def test_get_payment_missing(client, payment_data):
    response = await client.get(
        f"{payments_url(payment_data)}/{uuid4()}",
        headers=payment_data["headers"]["owner"],
    )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_get_payment_outsider(client, payment_data):
    created = await create_payment(client, payment_data)

    response = await client.get(
        f"{payments_url(payment_data)}/{created['id']}",
        headers=payment_data["headers"]["outsider"],
    )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_get_payment_cannot_use_another_organization(
    client, payment_data
):
    created = await create_payment(client, payment_data)

    # Пользователь имеет доступ к другой организации,
    # но пытается получить через неё чужой платёж.
    other_url = payments_url(
        payment_data, payment_data["other_organization_id"]
    )
    response = await client.get(
        f"{other_url}/{created['id']}",
        headers=payment_data["headers"]["outsider"],
    )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "manager", "viewer"])
async def test_list_payments_success(client, payment_data, role):
    created = await create_payment(client, payment_data)

    # Добавляем платёж другого счёта той же организации.
    response = await client.post(
        payments_url(payment_data),
        headers=payment_data["headers"]["owner"],
        json={"invoice_id": str(payment_data["empty_invoice_id"])},
    )
    assert response.status_code == 201, response.text

    # И платёж другой организации.
    response = await client.post(
        payments_url(
            payment_data, payment_data["other_organization_id"]
        ),
        headers=payment_data["headers"]["outsider"],
        json={"invoice_id": str(payment_data["other_invoice_id"])},
    )
    assert response.status_code == 201, response.text

    response = await client.get(
        payments_url(payment_data),
        headers=payment_data["headers"][role],
        params={"invoice_id": str(payment_data["invoice_id"])},
    )

    assert response.status_code == 200, response.text
    assert response.json() == [created]


@pytest.mark.asyncio
async def test_list_payments_empty(client, payment_data):
    response = await client.get(
        payments_url(payment_data),
        headers=payment_data["headers"]["owner"],
        params={"invoice_id": str(payment_data["empty_invoice_id"])},
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["missing", "other_organization"])
async def test_list_payments_unavailable_invoice(
    client, payment_data, target
):
    invoice_id = (
        uuid4()
        if target == "missing"
        else payment_data["other_invoice_id"]
    )

    response = await client.get(
        payments_url(payment_data),
        headers=payment_data["headers"]["owner"],
        params={"invoice_id": str(invoice_id)},
    )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_list_payments_outsider(client, payment_data):
    await create_payment(client, payment_data)

    response = await client.get(
        payments_url(payment_data),
        headers=payment_data["headers"]["outsider"],
        params={"invoice_id": str(payment_data["invoice_id"])},
    )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "get", "list"])
async def test_payments_require_authentication(
    client, db_session, payment_data, operation
):
    created = await create_payment(client, payment_data)
    before = await read_payments(
        db_session, payment_data["organization_id"]
    )
    url = payments_url(payment_data)

    if operation == "create":
        response = await client.post(
            url,
            json={"invoice_id": str(payment_data["empty_invoice_id"])},
        )
    elif operation == "get":
        response = await client.get(f"{url}/{created['id']}")
    else:
        response = await client.get(
            url,
            params={"invoice_id": str(payment_data["invoice_id"])},
        )

    assert response.status_code == 401, response.text
    assert await read_payments(
        db_session, payment_data["organization_id"]
    ) == before
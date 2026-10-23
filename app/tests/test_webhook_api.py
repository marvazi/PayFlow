from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update

from app.api.dependencies import get_psp_client
from app.core.config import settings
from app.main import app
from app.models import Customer, Organization
from app.models.invoice import Invoice
from app.models.payment import Payment

WEBHOOK_URL = "/webhooks/psp"
TEST_SECRET = "test-webhook-secret-" + "a" * 32

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def webhook_dependencies(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", TEST_SECRET)

    psp_client = AsyncMock()

    async def override_psp_client():
        yield psp_client

    previous = app.dependency_overrides.get(get_psp_client)
    app.dependency_overrides[get_psp_client] = override_psp_client

    try:
        yield psp_client
        # При обработке вебхука запросы обратно в PSP не нужны.
        assert psp_client.mock_calls == []
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_psp_client, None)
        else:
            app.dependency_overrides[get_psp_client] = previous


@pytest.fixture
def webhook_headers():
    return {"X-Webhook-Secret": TEST_SECRET}


@pytest_asyncio.fixture
async def webhook_data(db_session):
    organization_id = uuid4()
    customer_id = uuid4()
    invoice_id = uuid4()
    payment_id = uuid4()
    transaction_id = uuid4()

    try:
        db_session.add(
            Organization(
                id=organization_id,
                name=f"Webhook-{uuid4()}",
            )
        )
        await db_session.flush()

        db_session.add(
            Customer(
                id=customer_id,
                organization_id=organization_id,
                name="Webhook customer",
                email=f"{uuid4()}@example.com",
            )
        )
        await db_session.flush()

        db_session.add(
            Invoice(
                id=invoice_id,
                organization_id=organization_id,
                customer_id=customer_id,
                description="Webhook test",
                amount_minor=150050,
                currency="RUB",
                status="issued",
            )
        )
        await db_session.flush()

        db_session.add(
            Payment(
                id=payment_id,
                organization_id=organization_id,
                invoice_id=invoice_id,
                provider_transaction_id=transaction_id,
                amount_minor=150050,
                currency="RUB",
                status="pending",
            )
        )
        await db_session.commit()

        yield {
            "payment_id": payment_id,
            "invoice_id": invoice_id,
            "transaction_id": transaction_id,
            "payload": {
                "transaction_id": str(transaction_id),
                "external_payment_id": str(payment_id),
                "amount_minor": 150050,
                "currency": "RUB",
                "status": "succeeded",
            },
        }
    finally:
        await db_session.rollback()

        for model in (Payment, Invoice, Customer):
            await db_session.execute(
                delete(model).where(model.organization_id == organization_id)
            )

        await db_session.execute(
            delete(Organization).where(Organization.id == organization_id)
        )
        await db_session.commit()


async def read_state(db_session, data):
    """Читаем данные из БД и закрываем транзакцию чтения."""
    await db_session.rollback()

    try:
        result = await db_session.execute(
            select(
                Payment.status.label("payment_status"),
                Payment.provider_transaction_id,
                Payment.amount_minor,
                Payment.currency,
                Payment.updated_at,
                Invoice.status.label("invoice_status"),
            )
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .where(Payment.id == data["payment_id"])
        )
        return dict(result.mappings().one())
    finally:
        await db_session.rollback()


@pytest.mark.parametrize(
    ("payment_status", "invoice_status"),
    [
        ("succeeded", "paid"),
        ("failed", "issued"),
    ],
)
async def test_webhook_applies_result(
    client,
    db_session,
    webhook_data,
    webhook_headers,
    payment_status,
    invoice_status,
):
    payload = {
        **webhook_data["payload"],
        "status": payment_status,
    }

    response = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json=payload,
    )

    assert response.status_code == 204, response.text
    assert response.content == b""

    state = await read_state(db_session, webhook_data)
    assert state["payment_status"] == payment_status
    assert state["invoice_status"] == invoice_status
    assert state["provider_transaction_id"] == webhook_data["transaction_id"]


@pytest.mark.parametrize("status", ["succeeded", "failed"])
async def test_webhook_repeat_does_not_change_data(
    client,
    db_session,
    webhook_data,
    webhook_headers,
    status,
):
    payload = {**webhook_data["payload"], "status": status}

    first = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json=payload,
    )
    assert first.status_code == 204, first.text

    before = await read_state(db_session, webhook_data)

    second = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json=payload,
    )

    assert second.status_code == 204, second.text
    assert second.content == b""
    assert await read_state(db_session, webhook_data) == before


@pytest.mark.parametrize(
    ("first_status", "second_status"),
    [
        ("succeeded", "failed"),
        ("failed", "succeeded"),
    ],
)
async def test_webhook_rejects_opposite_final_status(
    client,
    db_session,
    webhook_data,
    webhook_headers,
    first_status,
    second_status,
):
    first = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json={**webhook_data["payload"], "status": first_status},
    )
    assert first.status_code == 204, first.text

    before = await read_state(db_session, webhook_data)

    second = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json={**webhook_data["payload"], "status": second_status},
    )

    assert second.status_code == 409, second.text
    assert await read_state(db_session, webhook_data) == before


@pytest.mark.parametrize("already_completed", [False, True])
@pytest.mark.parametrize("field", ["amount_minor", "transaction_id"])
async def test_webhook_rejects_mismatched_data_even_on_repeat(
    client,
    db_session,
    webhook_data,
    webhook_headers,
    already_completed,
    field,
):
    if already_completed:
        response = await client.post(
            WEBHOOK_URL,
            headers=webhook_headers,
            json=webhook_data["payload"],
        )
        assert response.status_code == 204, response.text

    before = await read_state(db_session, webhook_data)

    payload = dict(webhook_data["payload"])
    payload[field] = 1 if field == "amount_minor" else str(uuid4())

    response = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json=payload,
    )

    assert response.status_code == 409, response.text
    assert await read_state(db_session, webhook_data) == before


@pytest.mark.parametrize("status", ["succeeded", "failed"])
async def test_webhook_saves_missing_provider_id(
    client,
    db_session,
    webhook_data,
    webhook_headers,
    status,
):
    await db_session.execute(
        update(Payment)
        .where(Payment.id == webhook_data["payment_id"])
        .values(provider_transaction_id=None)
    )
    await db_session.commit()

    response = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json={**webhook_data["payload"], "status": status},
    )

    assert response.status_code == 204, response.text

    state = await read_state(db_session, webhook_data)
    assert state["provider_transaction_id"] == webhook_data["transaction_id"]
    assert state["payment_status"] == status
    assert state["invoice_status"] == ("paid" if status == "succeeded" else "issued")


@pytest.mark.parametrize("invoice_status", ["draft", "cancelled", "paid"])
async def test_webhook_rolls_back_provider_id_when_invoice_invalid(
    client,
    db_session,
    webhook_data,
    webhook_headers,
    invoice_status,
):
    await db_session.execute(
        update(Payment)
        .where(Payment.id == webhook_data["payment_id"])
        .values(provider_transaction_id=None)
    )
    await db_session.execute(
        update(Invoice)
        .where(Invoice.id == webhook_data["invoice_id"])
        .values(status=invoice_status)
    )
    await db_session.commit()

    before = await read_state(db_session, webhook_data)

    response = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json=webhook_data["payload"],
    )

    assert response.status_code == 409, response.text
    # Проверяем откат всего изменения, включая привязку ID PSP.
    assert await read_state(db_session, webhook_data) == before


async def test_webhook_unknown_payment(
    client,
    db_session,
    webhook_data,
    webhook_headers,
):
    before = await read_state(db_session, webhook_data)

    response = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json={
            **webhook_data["payload"],
            "external_payment_id": str(uuid4()),
        },
    )

    assert response.status_code == 404, response.text
    assert await read_state(db_session, webhook_data) == before


@pytest.mark.parametrize("secret", [None, "wrong-secret"])
async def test_webhook_requires_correct_secret(
    client,
    db_session,
    webhook_data,
    secret,
):
    before = await read_state(db_session, webhook_data)
    headers = {} if secret is None else {"X-Webhook-Secret": secret}

    response = await client.post(
        WEBHOOK_URL,
        headers=headers,
        json=webhook_data["payload"],
    )

    assert response.status_code == 401, response.text
    assert await read_state(db_session, webhook_data) == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "pending"),
        ("currency", "USD"),
        ("amount_minor", 0),
        ("amount_minor", -1),
        ("amount_minor", "150050"),
        ("amount_minor", True),
        ("amount_minor", 9_223_372_036_854_775_808),
        ("transaction_id", "not-a-uuid"),
        ("external_payment_id", "not-a-uuid"),
    ],
)
async def test_webhook_validates_payload(
    client,
    db_session,
    webhook_data,
    webhook_headers,
    field,
    value,
):
    before = await read_state(db_session, webhook_data)

    response = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json={**webhook_data["payload"], field: value},
    )

    assert response.status_code == 422, response.text
    assert await read_state(db_session, webhook_data) == before


async def test_webhook_requires_payload_fields(
    client,
    webhook_headers,
):
    response = await client.post(
        WEBHOOK_URL,
        headers=webhook_headers,
        json={},
    )

    assert response.status_code == 422, response.text

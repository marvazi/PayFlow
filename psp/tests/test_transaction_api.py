from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from psp.core.config import settings
from psp.models import Transaction

pytestmark = pytest.mark.asyncio


async def create_transaction(client, headers, payload):
    response = await client.post(
        "/transactions",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def read_transactions(factory, external_payment_id):
    async with factory() as session:
        result = await session.execute(
            select(
                Transaction.id,
                Transaction.external_payment_id,
                Transaction.amount_minor,
                Transaction.currency,
                Transaction.status,
                Transaction.created_at,
                Transaction.updated_at,
            )
            .where(Transaction.external_payment_id == UUID(external_payment_id))
            .order_by(Transaction.id)
        )
        return [dict(row) for row in result.mappings().all()]


async def test_create_transaction(
    psp_client,
    psp_headers,
    transaction_payload,
    psp_session_factory,
):
    body = await create_transaction(psp_client, psp_headers, transaction_payload)

    assert body["external_payment_id"] == transaction_payload["external_payment_id"]
    assert body["amount_minor"] == 150050
    assert body["currency"] == "RUB"
    assert body["status"] == "pending"
    assert body["created_at"]
    assert body["updated_at"]

    rows = await read_transactions(
        psp_session_factory,
        transaction_payload["external_payment_id"],
    )

    assert len(rows) == 1
    assert rows[0]["id"] == UUID(body["id"])
    assert rows[0]["external_payment_id"] == UUID(
        transaction_payload["external_payment_id"]
    )
    assert rows[0]["amount_minor"] == 150050
    assert rows[0]["currency"] == "RUB"
    assert rows[0]["status"] == "pending"


async def test_create_transaction_is_idempotent(
    psp_client,
    psp_headers,
    transaction_payload,
    psp_session_factory,
):
    first = await create_transaction(psp_client, psp_headers, transaction_payload)
    before = await read_transactions(
        psp_session_factory,
        transaction_payload["external_payment_id"],
    )

    second = await create_transaction(psp_client, psp_headers, transaction_payload)

    assert second == first
    assert (
        await read_transactions(
            psp_session_factory,
            transaction_payload["external_payment_id"],
        )
        == before
    )


async def test_create_transaction_conflicting_amount(
    psp_client,
    psp_headers,
    transaction_payload,
    psp_session_factory,
):
    await create_transaction(psp_client, psp_headers, transaction_payload)
    before = await read_transactions(
        psp_session_factory,
        transaction_payload["external_payment_id"],
    )

    response = await psp_client.post(
        "/transactions",
        headers=psp_headers,
        json={**transaction_payload, "amount_minor": 999},
    )

    assert response.status_code == 409, response.text
    assert (
        await read_transactions(
            psp_session_factory,
            transaction_payload["external_payment_id"],
        )
        == before
    )


async def test_get_transaction(psp_client, psp_headers, transaction_payload):
    created = await create_transaction(psp_client, psp_headers, transaction_payload)

    response = await psp_client.get(
        f"/transactions/{created['id']}",
        headers=psp_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == created


@pytest.mark.parametrize("operation", ["get", "complete"])
async def test_missing_transaction(psp_client, psp_headers, operation):
    url = f"/transactions/{uuid4()}"

    if operation == "get":
        response = await psp_client.get(url, headers=psp_headers)
    else:
        response = await psp_client.post(
            f"{url}/complete",
            headers=psp_headers,
            json={"status": "succeeded"},
        )

    assert response.status_code == 404, response.text


@pytest.mark.parametrize("status", ["succeeded", "failed"])
async def test_complete_transaction(
    psp_client,
    psp_headers,
    transaction_payload,
    psp_session_factory,
    status,
):
    created = await create_transaction(psp_client, psp_headers, transaction_payload)
    before = await read_transactions(
        psp_session_factory,
        transaction_payload["external_payment_id"],
    )

    response = await psp_client.post(
        f"/transactions/{created['id']}/complete",
        headers=psp_headers,
        json={"status": status},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == created["id"]
    assert body["status"] == status

    after = await read_transactions(
        psp_session_factory,
        transaction_payload["external_payment_id"],
    )

    assert len(after) == 1
    assert after[0]["status"] == status
    assert after[0]["updated_at"] >= before[0]["updated_at"]
    assert after[0] == {
        **before[0],
        "status": status,
        "updated_at": after[0]["updated_at"],
    }


@pytest.mark.parametrize("status", ["succeeded", "failed"])
async def test_complete_transaction_is_idempotent(
    psp_client,
    psp_headers,
    transaction_payload,
    psp_session_factory,
    status,
):
    created = await create_transaction(psp_client, psp_headers, transaction_payload)
    url = f"/transactions/{created['id']}/complete"

    first = await psp_client.post(
        url,
        headers=psp_headers,
        json={"status": status},
    )
    assert first.status_code == 200, first.text

    before = await read_transactions(
        psp_session_factory,
        transaction_payload["external_payment_id"],
    )

    second = await psp_client.post(
        url,
        headers=psp_headers,
        json={"status": status},
    )

    assert second.status_code == 200, second.text
    assert second.json() == first.json()
    assert (
        await read_transactions(
            psp_session_factory,
            transaction_payload["external_payment_id"],
        )
        == before
    )


@pytest.mark.parametrize(
    ("first_status", "second_status"),
    [
        ("succeeded", "failed"),
        ("failed", "succeeded"),
    ],
)
async def test_complete_transaction_rejects_conflicting_result(
    psp_client,
    psp_headers,
    transaction_payload,
    psp_session_factory,
    first_status,
    second_status,
):
    created = await create_transaction(psp_client, psp_headers, transaction_payload)
    url = f"/transactions/{created['id']}/complete"

    first = await psp_client.post(
        url,
        headers=psp_headers,
        json={"status": first_status},
    )
    assert first.status_code == 200, first.text

    before = await read_transactions(
        psp_session_factory,
        transaction_payload["external_payment_id"],
    )

    response = await psp_client.post(
        url,
        headers=psp_headers,
        json={"status": second_status},
    )

    assert response.status_code == 409, response.text
    assert (
        await read_transactions(
            psp_session_factory,
            transaction_payload["external_payment_id"],
        )
        == before
    )


@pytest.mark.parametrize("status", ["succeeded", "failed"])
async def test_create_repeat_preserves_completed_status(
    psp_client,
    psp_headers,
    transaction_payload,
    psp_session_factory,
    status,
):
    created = await create_transaction(psp_client, psp_headers, transaction_payload)

    completed = await psp_client.post(
        f"/transactions/{created['id']}/complete",
        headers=psp_headers,
        json={"status": status},
    )
    assert completed.status_code == 200, completed.text

    before = await read_transactions(
        psp_session_factory,
        transaction_payload["external_payment_id"],
    )

    repeated = await create_transaction(psp_client, psp_headers, transaction_payload)

    assert repeated == completed.json()
    assert (
        await read_transactions(
            psp_session_factory,
            transaction_payload["external_payment_id"],
        )
        == before
    )


@pytest.mark.parametrize("operation", ["create", "get", "complete"])
@pytest.mark.parametrize("key_kind", ["missing", "wrong"])
async def test_api_key_is_required(
    psp_client,
    psp_headers,
    transaction_payload,
    psp_session_factory,
    operation,
    key_kind,
):
    created = await create_transaction(psp_client, psp_headers, transaction_payload)
    before = await read_transactions(
        psp_session_factory,
        transaction_payload["external_payment_id"],
    )

    headers = (
        {} if key_kind == "missing" else {"X-API-Key": settings.api_key + "-wrong"}
    )

    if operation == "create":
        response = await psp_client.post(
            "/transactions",
            headers=headers,
            json=transaction_payload,
        )
    elif operation == "get":
        response = await psp_client.get(
            f"/transactions/{created['id']}",
            headers=headers,
        )
    else:
        response = await psp_client.post(
            f"/transactions/{created['id']}/complete",
            headers=headers,
            json={"status": "succeeded"},
        )

    assert response.status_code == 401, response.text
    assert (
        await read_transactions(
            psp_session_factory,
            transaction_payload["external_payment_id"],
        )
        == before
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount_minor", 0),
        ("amount_minor", -1),
        ("amount_minor", 1.5),
        ("amount_minor", "100"),
        ("amount_minor", True),
        ("amount_minor", None),
        ("amount_minor", 9_223_372_036_854_775_808),
        ("currency", "USD"),
        ("external_payment_id", "not-a-uuid"),
        ("external_payment_id", None),
        ("status", "succeeded"),
        ("unknown_field", "value"),
    ],
)
async def test_create_transaction_invalid_payload(
    psp_client,
    psp_headers,
    transaction_payload,
    psp_session_factory,
    field,
    value,
):
    response = await psp_client.post(
        "/transactions",
        headers=psp_headers,
        json={**transaction_payload, field: value},
    )

    assert response.status_code == 422, response.text
    assert (
        await read_transactions(
            psp_session_factory,
            transaction_payload["external_payment_id"],
        )
        == []
    )


@pytest.mark.parametrize(
    "field",
    ["external_payment_id", "amount_minor", "currency"],
)
async def test_create_transaction_missing_field(
    psp_client, psp_headers, transaction_payload, field
):
    payload = transaction_payload.copy()
    payload.pop(field)

    response = await psp_client.post(
        "/transactions",
        headers=psp_headers,
        json=payload,
    )

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("amount", [1, 9_223_372_036_854_775_807])
async def test_create_transaction_amount_boundaries(
    psp_client,
    psp_headers,
    transaction_payload,
    amount,
):
    body = await create_transaction(
        psp_client,
        psp_headers,
        {**transaction_payload, "amount_minor": amount},
    )

    assert body["amount_minor"] == amount


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"status": None},
        {"status": "pending"},
        {"status": "paid"},
        {"status": "cancelled"},
        {"status": "succeeded", "amount_minor": 1},
    ],
)
async def test_complete_transaction_invalid_payload(
    psp_client,
    psp_headers,
    transaction_payload,
    psp_session_factory,
    payload,
):
    created = await create_transaction(psp_client, psp_headers, transaction_payload)
    before = await read_transactions(
        psp_session_factory,
        transaction_payload["external_payment_id"],
    )

    response = await psp_client.post(
        f"/transactions/{created['id']}/complete",
        headers=psp_headers,
        json=payload,
    )

    assert response.status_code == 422, response.text
    assert (
        await read_transactions(
            psp_session_factory,
            transaction_payload["external_payment_id"],
        )
        == before
    )

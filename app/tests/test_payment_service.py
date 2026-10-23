from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update

from app.core.exeptions import (
    InvalidInvoiceStatusError,
    InvalidPaymentStatusError,
    PaymentNotFoundError,
    PaymentWebhookConflictError,
)
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.organization import Organization
from app.models.payment import Payment
from app.schemas.payment import PaymentWebhookPayload
from app.services.payment import PaymentService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def payment_service(db_session):
    psp_client = AsyncMock()
    service = PaymentService(
        session=db_session,
        psp_client=psp_client,
    )

    yield service

    # Приём webhook не должен выполнять запросы в PSP.
    assert psp_client.mock_calls == []


@pytest_asyncio.fixture
async def payment_case(db_session):
    organization_id = uuid4()
    customer_id = uuid4()
    invoice_id = uuid4()
    payment_id = uuid4()
    provider_transaction_id = uuid4()

    try:
        db_session.add(
            Organization(
                id=organization_id,
                name=f"Test-{uuid4()}",
            )
        )
        await db_session.flush()

        db_session.add(
            Customer(
                id=customer_id,
                organization_id=organization_id,
                name="Тестовый клиент",
                email=f"{uuid4()}@example.com",
            )
        )
        await db_session.flush()

        db_session.add(
            Invoice(
                id=invoice_id,
                organization_id=organization_id,
                customer_id=customer_id,
                description="Тестовый счёт",
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
                provider_transaction_id=provider_transaction_id,
                amount_minor=150050,
                currency="RUB",
                status="pending",
            )
        )
        await db_session.commit()

        yield {
            "organization_id": organization_id,
            "invoice_id": invoice_id,
            "payment_id": payment_id,
            "provider_transaction_id": provider_transaction_id,
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


def make_payload(case, result_status="succeeded", **changes):
    data = {
        "transaction_id": case["provider_transaction_id"],
        "external_payment_id": case["payment_id"],
        "amount_minor": 150050,
        "currency": "RUB",
        "status": result_status,
    }
    data.update(changes)
    return PaymentWebhookPayload.model_validate(data)


async def read_state(db_session, case):
    """Читаем сохранённые значения, а не состояние ORM-объектов."""
    await db_session.rollback()

    try:
        payment_result = await db_session.execute(
            select(
                Payment.id,
                Payment.organization_id,
                Payment.invoice_id,
                Payment.provider_transaction_id,
                Payment.amount_minor,
                Payment.currency,
                Payment.status,
                Payment.created_at,
                Payment.updated_at,
            ).where(Payment.id == case["payment_id"])
        )

        invoice_result = await db_session.execute(
            select(
                Invoice.id,
                Invoice.organization_id,
                Invoice.customer_id,
                Invoice.description,
                Invoice.amount_minor,
                Invoice.currency,
                Invoice.status,
                Invoice.created_at,
            ).where(Invoice.id == case["invoice_id"])
        )

        return {
            "payment": dict(payment_result.mappings().one()),
            "invoice": dict(invoice_result.mappings().one()),
        }
    finally:
        await db_session.rollback()


@pytest.mark.parametrize(
    ("result_status", "invoice_status"),
    [
        ("succeeded", "paid"),
        ("failed", "issued"),
    ],
)
async def test_process_result_success(
    db_session,
    payment_case,
    payment_service,
    result_status,
    invoice_status,
):
    before = await read_state(db_session, payment_case)

    payment = await payment_service.process_result(
        payload=make_payload(payment_case, result_status),
    )

    assert payment.id == payment_case["payment_id"]
    assert payment.status == result_status

    after = await read_state(db_session, payment_case)

    assert after["payment"]["updated_at"] >= before["payment"]["updated_at"]
    assert after["payment"] == {
        **before["payment"],
        "status": result_status,
        "updated_at": after["payment"]["updated_at"],
    }
    assert after["invoice"] == {
        **before["invoice"],
        "status": invoice_status,
    }


@pytest.mark.parametrize("result_status", ["succeeded", "failed"])
async def test_process_result_is_idempotent(
    db_session,
    payment_case,
    payment_service,
    result_status,
):
    payload = make_payload(payment_case, result_status)

    await payment_service.process_result(payload=payload)
    before = await read_state(db_session, payment_case)

    payment = await payment_service.process_result(payload=payload)

    assert payment.status == result_status
    assert await read_state(db_session, payment_case) == before


@pytest.mark.parametrize(
    ("first_status", "second_status"),
    [
        ("succeeded", "failed"),
        ("failed", "succeeded"),
    ],
)
async def test_process_result_rejects_conflicting_result(
    db_session,
    payment_case,
    payment_service,
    first_status,
    second_status,
):
    await payment_service.process_result(
        payload=make_payload(payment_case, first_status),
    )
    before = await read_state(db_session, payment_case)

    with pytest.raises(InvalidPaymentStatusError):
        await payment_service.process_result(
            payload=make_payload(payment_case, second_status),
        )

    assert await read_state(db_session, payment_case) == before


@pytest.mark.parametrize(
    "invalid_status",
    ["pending", "paid", "cancelled", "", "SUCCEEDED"],
)
async def test_process_result_rejects_invalid_status(
    db_session,
    payment_case,
    payment_service,
    invalid_status,
):
    before = await read_state(db_session, payment_case)

    # Намеренно обходим Pydantic: проверяем защиту самого сервиса.
    # В HTTP-запросе такие значения должна отклонять схема.
    payload = PaymentWebhookPayload.model_construct(
        transaction_id=payment_case["provider_transaction_id"],
        external_payment_id=payment_case["payment_id"],
        amount_minor=150050,
        currency="RUB",
        status=invalid_status,
    )

    with pytest.raises(InvalidPaymentStatusError):
        await payment_service.process_result(payload=payload)

    assert await read_state(db_session, payment_case) == before


@pytest.mark.parametrize("result_status", ["succeeded", "failed"])
@pytest.mark.parametrize("invoice_status", ["draft", "paid", "cancelled"])
async def test_process_result_rejects_invalid_invoice_status(
    db_session,
    payment_case,
    payment_service,
    result_status,
    invoice_status,
):
    await db_session.execute(
        update(Invoice)
        .where(Invoice.id == payment_case["invoice_id"])
        .values(status=invoice_status)
    )
    await db_session.commit()

    before = await read_state(db_session, payment_case)

    with pytest.raises(InvalidInvoiceStatusError):
        await payment_service.process_result(
            payload=make_payload(payment_case, result_status),
        )

    assert await read_state(db_session, payment_case) == before


async def test_process_result_missing_payment(
    db_session,
    payment_case,
    payment_service,
):
    before = await read_state(db_session, payment_case)

    with pytest.raises(PaymentNotFoundError):
        await payment_service.process_result(
            payload=make_payload(
                payment_case,
                external_payment_id=uuid4(),
            ),
        )

    assert await read_state(db_session, payment_case) == before


@pytest.mark.parametrize("already_completed", [False, True])
@pytest.mark.parametrize("field", ["amount_minor", "transaction_id"])
async def test_process_result_rejects_mismatched_payload(
    db_session,
    payment_case,
    payment_service,
    already_completed,
    field,
):
    if already_completed:
        await payment_service.process_result(
            payload=make_payload(payment_case),
        )

    before = await read_state(db_session, payment_case)
    changes = (
        {"amount_minor": 150051}
        if field == "amount_minor"
        else {"transaction_id": uuid4()}
    )

    with pytest.raises(PaymentWebhookConflictError):
        await payment_service.process_result(
            payload=make_payload(payment_case, **changes),
        )

    assert await read_state(db_session, payment_case) == before


async def test_process_result_rejects_currency_mismatch(
    db_session,
    payment_case,
    payment_service,
):
    before = await read_state(db_session, payment_case)

    # Через API USD не пройдёт Literal["RUB"].
    # Здесь отдельно проверяем сравнение валют в сервисе.
    payload = PaymentWebhookPayload.model_construct(
        transaction_id=payment_case["provider_transaction_id"],
        external_payment_id=payment_case["payment_id"],
        amount_minor=150050,
        currency="USD",  # type: ignore[arg-type]
        status="succeeded",
    )

    with pytest.raises(PaymentWebhookConflictError):
        await payment_service.process_result(payload=payload)

    assert await read_state(db_session, payment_case) == before


@pytest.mark.parametrize(
    ("result_status", "invoice_status"),
    [
        ("succeeded", "paid"),
        ("failed", "issued"),
    ],
)
async def test_process_result_sets_missing_provider_id(
    db_session,
    payment_case,
    payment_service,
    result_status,
    invoice_status,
):
    await db_session.execute(
        update(Payment)
        .where(Payment.id == payment_case["payment_id"])
        .values(provider_transaction_id=None)
    )
    await db_session.commit()

    await payment_service.process_result(
        payload=make_payload(payment_case, result_status),
    )

    after = await read_state(db_session, payment_case)

    assert (
        after["payment"]["provider_transaction_id"]
        == payment_case["provider_transaction_id"]
    )
    assert after["payment"]["status"] == result_status
    assert after["invoice"]["status"] == invoice_status


@pytest.mark.parametrize("missing_provider_id", [False, True])
async def test_process_result_rolls_back_all_updates(
    db_session,
    payment_case,
    payment_service,
    monkeypatch,
    missing_provider_id,
):
    if missing_provider_id:
        await db_session.execute(
            update(Payment)
            .where(Payment.id == payment_case["payment_id"])
            .values(provider_transaction_id=None)
        )
        await db_session.commit()

    before = await read_state(db_session, payment_case)
    original_update_status = payment_service.payment_repository.update_status

    async def update_then_fail(payment, status):
        await original_update_status(payment=payment, status=status)
        raise RuntimeError("Имитируем сбой после обновления")

    monkeypatch.setattr(
        payment_service.payment_repository,
        "update_status",
        update_then_fail,
    )

    with pytest.raises(
        RuntimeError,
        match="Имитируем сбой после обновления",
    ):
        await payment_service.process_result(
            payload=make_payload(payment_case),
        )

    # Откатываются статус счёта, статус платежа и привязка PSP ID.
    assert await read_state(db_session, payment_case) == before

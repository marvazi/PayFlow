from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update

from app.core.exeptions import (
    InvalidInvoiceStatusError,
    InvalidPaymentStatusError,
    PaymentNotFoundError,
)
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.organization import Organization
from app.models.payment import Payment
from app.services.payment import PaymentService


@pytest_asyncio.fixture
async def payment_case(db_session):
    organization_id = uuid4()
    other_organization_id = uuid4()
    customer_id = uuid4()
    invoice_id = uuid4()
    payment_id = uuid4()

    organization_ids = [organization_id, other_organization_id]

    try:
        db_session.add_all(
            [
                Organization(
                    id=organization_id,
                    name=f"Test-{uuid4()}",
                ),
                Organization(
                    id=other_organization_id,
                    name=f"Test-{uuid4()}",
                ),
            ]
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
                amount_minor=150050,
                currency="RUB",
                status="pending",
            )
        )
        await db_session.commit()

        yield {
            "organization_id": organization_id,
            "other_organization_id": other_organization_id,
            "invoice_id": invoice_id,
            "payment_id": payment_id,
        }

    finally:
        await db_session.rollback()

        for model in (Payment, Invoice, Customer):
            await db_session.execute(
                delete(model).where(model.organization_id.in_(organization_ids))
            )

        await db_session.execute(
            delete(Organization).where(Organization.id.in_(organization_ids))
        )
        await db_session.commit()


async def read_state(db_session, case):
    """Читаем сохранённые значения напрямую из БД."""
    await db_session.rollback()

    try:
        payment_result = await db_session.execute(
            select(
                Payment.id,
                Payment.organization_id,
                Payment.invoice_id,
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
        # Следующий вызов сервиса сможет открыть свою транзакцию.
        await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result_status", "invoice_status"),
    [
        ("succeeded", "paid"),
        ("failed", "issued"),
    ],
)
async def test_process_result_success(
    db_session, payment_case, result_status, invoice_status
):
    before = await read_state(db_session, payment_case)
    service = PaymentService(db_session)

    payment = await service.process_result(
        organization_id=payment_case["organization_id"],
        payment_id=payment_case["payment_id"],
        status=result_status,
    )

    assert payment.id == payment_case["payment_id"]
    assert payment.status == result_status
    assert payment.updated_at is not None

    after = await read_state(db_session, payment_case)

    assert after["payment"]["status"] == result_status
    assert after["invoice"]["status"] == invoice_status
    assert after["payment"]["updated_at"] >= before["payment"]["updated_at"]

    # Другие поля не должны меняться.
    expected_payment = {
        **before["payment"],
        "status": result_status,
        "updated_at": after["payment"]["updated_at"],
    }
    expected_invoice = {
        **before["invoice"],
        "status": invoice_status,
    }

    assert after["payment"] == expected_payment
    assert after["invoice"] == expected_invoice


@pytest.mark.asyncio
@pytest.mark.parametrize("result_status", ["succeeded", "failed"])
async def test_process_result_is_idempotent(db_session, payment_case, result_status):
    service = PaymentService(db_session)

    await service.process_result(
        organization_id=payment_case["organization_id"],
        payment_id=payment_case["payment_id"],
        status=result_status,
    )
    before = await read_state(db_session, payment_case)

    payment = await service.process_result(
        organization_id=payment_case["organization_id"],
        payment_id=payment_case["payment_id"],
        status=result_status,
    )

    assert payment.status == result_status

    after = await read_state(db_session, payment_case)

    # Повтор не меняет даже updated_at.
    assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("first_status", "second_status"),
    [
        ("succeeded", "failed"),
        ("failed", "succeeded"),
    ],
)
async def test_process_result_rejects_conflicting_result(
    db_session, payment_case, first_status, second_status
):
    service = PaymentService(db_session)

    await service.process_result(
        organization_id=payment_case["organization_id"],
        payment_id=payment_case["payment_id"],
        status=first_status,
    )
    before = await read_state(db_session, payment_case)

    with pytest.raises(InvalidPaymentStatusError):
        await service.process_result(
            organization_id=payment_case["organization_id"],
            payment_id=payment_case["payment_id"],
            status=second_status,
        )

    assert await read_state(db_session, payment_case) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_status",
    ["pending", "paid", "cancelled", "", "SUCCEEDED"],
)
async def test_process_result_rejects_invalid_status(
    db_session, payment_case, invalid_status
):
    before = await read_state(db_session, payment_case)
    service = PaymentService(db_session)

    with pytest.raises(InvalidPaymentStatusError):
        await service.process_result(
            organization_id=payment_case["organization_id"],
            payment_id=payment_case["payment_id"],
            status=invalid_status,
        )

    assert await read_state(db_session, payment_case) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("result_status", ["succeeded", "failed"])
@pytest.mark.parametrize("invoice_status", ["draft", "paid", "cancelled"])
async def test_process_result_rejects_invalid_invoice_status(
    db_session, payment_case, result_status, invoice_status
):
    # Создаём некорректную комбинацию состояний напрямую,
    # чтобы проверить защиту сервисного метода.
    await db_session.execute(
        update(Invoice)
        .where(Invoice.id == payment_case["invoice_id"])
        .values(status=invoice_status)
    )
    await db_session.commit()

    before = await read_state(db_session, payment_case)
    service = PaymentService(db_session)

    with pytest.raises(InvalidInvoiceStatusError):
        await service.process_result(
            organization_id=payment_case["organization_id"],
            payment_id=payment_case["payment_id"],
            status=result_status,
        )

    assert await read_state(db_session, payment_case) == before


@pytest.mark.asyncio
async def test_process_result_missing_payment(db_session, payment_case):
    before = await read_state(db_session, payment_case)
    service = PaymentService(db_session)

    with pytest.raises(PaymentNotFoundError):
        await service.process_result(
            organization_id=payment_case["organization_id"],
            payment_id=uuid4(),
            status="succeeded",
        )

    assert await read_state(db_session, payment_case) == before


@pytest.mark.asyncio
async def test_process_result_other_organization(db_session, payment_case):
    before = await read_state(db_session, payment_case)
    service = PaymentService(db_session)

    with pytest.raises(PaymentNotFoundError):
        await service.process_result(
            organization_id=payment_case["other_organization_id"],
            payment_id=payment_case["payment_id"],
            status="succeeded",
        )

    assert await read_state(db_session, payment_case) == before


@pytest.mark.asyncio
async def test_process_result_rolls_back_both_updates(
    db_session, payment_case, monkeypatch
):
    before = await read_state(db_session, payment_case)
    service = PaymentService(db_session)

    original_update_status = service.payment_repository.update_status

    async def update_then_fail(payment, status):
        # Реально обновляем платёж и выполняем flush/refresh.
        # К этому моменту сервис уже обновил счёт.
        await original_update_status(payment=payment, status=status)
        raise RuntimeError("Имитируем сбой после обновления")

    monkeypatch.setattr(
        service.payment_repository,
        "update_status",
        update_then_fail,
    )

    with pytest.raises(
        RuntimeError,
        match="Имитируем сбой после обновления",
    ):
        await service.process_result(
            organization_id=payment_case["organization_id"],
            payment_id=payment_case["payment_id"],
            status="succeeded",
        )

    # Проверяем сохранённые данные, а не значения ORM-объектов.
    assert await read_state(db_session, payment_case) == before

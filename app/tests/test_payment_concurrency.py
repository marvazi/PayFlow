import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.core.exeptions import (
    InvalidInvoiceStatusError,
    InvoiceHasPendingPaymentError,
    PaymentAlreadyPendingError,
)
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import PaymentCreate
from app.services.invoice import InvoiceService
from app.services.payment import PaymentService


@pytest_asyncio.fixture
async def concurrent_case(concurrent_session_factory):
    factory = concurrent_session_factory

    owner_id = uuid4()
    organization_id = uuid4()
    customer_id = uuid4()
    invoice_id = uuid4()

    try:
        async with factory() as session:
            async with session.begin():
                session.add(
                    User(
                        id=owner_id,
                        name="Owner",
                        email=f"{owner_id}@example.com",
                        password_hash=None,
                    )
                )
                session.add(
                    Organization(
                        id=organization_id,
                        name=f"Test-{uuid4()}",
                    )
                )
                await session.flush()

                session.add(
                    Membership(
                        user_id=owner_id,
                        organization_id=organization_id,
                        role="owner",
                    )
                )
                session.add(
                    Customer(
                        id=customer_id,
                        organization_id=organization_id,
                        name="Клиент",
                        email=f"{uuid4()}@example.com",
                    )
                )
                await session.flush()

                session.add(
                    Invoice(
                        id=invoice_id,
                        organization_id=organization_id,
                        customer_id=customer_id,
                        description="Конкурентный тест",
                        amount_minor=150050,
                        currency="RUB",
                        status="issued",
                    )
                )

        yield {
            "owner_id": owner_id,
            "organization_id": organization_id,
            "invoice_id": invoice_id,
        }

    finally:
        async with factory() as session:
            async with session.begin():
                for model in (Payment, Invoice, Customer, Membership):
                    await session.execute(
                        delete(model).where(
                            model.organization_id == organization_id
                        )
                    )

                await session.execute(
                    delete(Organization).where(
                        Organization.id == organization_id
                    )
                )
                await session.execute(
                    delete(User).where(User.id == owner_id)
                )


def synchronize_before_invoice_lock(service, barrier, monkeypatch):
    """
    Оба вызова доходят до получения блокировки счёта,
    прежде чем продолжить выполнение.
    """
    original = service.invoice_repository.get_for_update

    async def synchronized_get(*args, **kwargs):
        await barrier.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(
        service.invoice_repository,
        "get_for_update",
        synchronized_get,
    )


async def run_concurrently(*operations):
    tasks = [
        asyncio.create_task(operation)
        for operation in operations
    ]

    try:
        return await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=15,
        )
    finally:
        # Даже при ошибке или таймауте завершаем операции
        # до очистки тестовых данных.
        for task in tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)


async def read_state(factory, case):
    # Новая сессия: проверяем результат в БД после транзакций.
    async with factory() as session:
        invoice_status = await session.scalar(
            select(Invoice.status).where(
                Invoice.id == case["invoice_id"]
            )
        )

        result = await session.execute(
            select(
                Payment.id,
                Payment.status,
                Payment.amount_minor,
                Payment.currency,
            ).where(
                Payment.invoice_id == case["invoice_id"],
                Payment.organization_id == case["organization_id"],
            )
        )
        payments = [dict(row) for row in result.mappings().all()]

    return invoice_status, payments


@pytest.mark.asyncio
async def test_concurrent_payment_creation(
    concurrent_session_factory,
    concurrent_case,
    monkeypatch,
):
    factory = concurrent_session_factory
    case = concurrent_case
    barrier = asyncio.Barrier(2)

    async def create():
        async with factory() as session:
            service = PaymentService(session)
            synchronize_before_invoice_lock(
                service, barrier, monkeypatch
            )

            payment = await service.create(
                actor_id=case["owner_id"],
                organization_id=case["organization_id"],
                data=PaymentCreate(invoice_id=case["invoice_id"]),
            )
            return payment.id

    results = await run_concurrently(create(), create())

    errors = [
        result for result in results
        if isinstance(result, BaseException)
    ]
    successful = [
        result for result in results
        if not isinstance(result, BaseException)
    ]

    assert len(successful) == 1, results
    assert len(errors) == 1, results
    assert isinstance(errors[0], PaymentAlreadyPendingError), results

    invoice_status, payments = await read_state(factory, case)

    assert invoice_status == "issued"
    assert len(payments) == 1
    assert payments[0]["id"] == successful[0]
    assert payments[0]["status"] == "pending"
    assert payments[0]["amount_minor"] == 150050
    assert payments[0]["currency"] == "RUB"


@pytest.mark.asyncio
async def test_concurrent_identical_payment_results(
    concurrent_session_factory,
    concurrent_case,
    monkeypatch,
):
    factory = concurrent_session_factory
    case = concurrent_case

    async with factory() as session:
        payment = await PaymentService(session).create(
            actor_id=case["owner_id"],
            organization_id=case["organization_id"],
            data=PaymentCreate(invoice_id=case["invoice_id"]),
        )
        payment_id = payment.id

    barrier = asyncio.Barrier(2)

    async def process():
        async with factory() as session:
            service = PaymentService(session)
            synchronize_before_invoice_lock(
                service, barrier, monkeypatch
            )

            payment = await service.process_result(
                organization_id=case["organization_id"],
                payment_id=payment_id,
                status="succeeded",
            )
            return payment.id, payment.status

    results = await run_concurrently(process(), process())

    assert results == [
        (payment_id, "succeeded"),
        (payment_id, "succeeded"),
    ], results

    invoice_status, payments = await read_state(factory, case)

    assert invoice_status == "paid"
    assert len(payments) == 1
    assert payments[0]["id"] == payment_id
    assert payments[0]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_concurrent_payment_creation_and_invoice_cancellation(
    concurrent_session_factory,
    concurrent_case,
    monkeypatch,
):
    factory = concurrent_session_factory
    case = concurrent_case
    barrier = asyncio.Barrier(2)

    async def create():
        async with factory() as session:
            service = PaymentService(session)
            synchronize_before_invoice_lock(
                service, barrier, monkeypatch
            )

            payment = await service.create(
                actor_id=case["owner_id"],
                organization_id=case["organization_id"],
                data=PaymentCreate(invoice_id=case["invoice_id"]),
            )
            return payment.id

    async def cancel():
        async with factory() as session:
            service = InvoiceService(session)
            synchronize_before_invoice_lock(
                service, barrier, monkeypatch
            )

            invoice = await service.cancel_invoice(
                actor_id=case["owner_id"],
                organization_id=case["organization_id"],
                invoice_id=case["invoice_id"],
            )
            return invoice.status

    create_result, cancel_result = await run_concurrently(
        create(), cancel()
    )

    invoice_status, payments = await read_state(factory, case)

    if isinstance(create_result, InvalidInvoiceStatusError):
        # Отмена получила блокировку первой.
        assert cancel_result == "cancelled"
        assert invoice_status == "cancelled"
        assert payments == []

    else:
        # Создание платежа получило блокировку первым.
        assert not isinstance(create_result, BaseException), create_result
        assert isinstance(
            cancel_result, InvoiceHasPendingPaymentError
        ), cancel_result

        assert invoice_status == "issued"
        assert len(payments) == 1
        assert payments[0]["id"] == create_result
        assert payments[0]["status"] == "pending"
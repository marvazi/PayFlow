from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exeptions import (
    OrganizationNotFoundError,
    PermissionDeniedError,
    PSPInvalidResponseError,
    PSPUnavailableError,
)
from app.models import Customer, Invoice, Membership, Organization, Payment, User
from app.schemas.payment import PaymentCreate
from app.services.payment import PaymentService


@pytest_asyncio.fixture
async def payment_case(
    db_session: AsyncSession,
) -> AsyncIterator[SimpleNamespace]:
    owner_id = uuid4()
    viewer_id = uuid4()
    outsider_id = uuid4()
    organization_id = uuid4()
    customer_id = uuid4()
    invoice_id = uuid4()

    try:
        users = [
            User(
                id=user_id,
                email=f"{user_id}@example.com",
                name=name,
                password_hash=None,
            )
            for user_id, name in (
                (owner_id, "Owner"),
                (viewer_id, "Viewer"),
                (outsider_id, "Outsider"),
            )
        ]
        db_session.add_all(users)
        db_session.add(
            Organization(
                id=organization_id,
                name=f"PSP test {organization_id}",
            )
        )
        await db_session.flush()

        db_session.add_all(
            [
                Membership(
                    user_id=owner_id,
                    organization_id=organization_id,
                    role="owner",
                ),
                Membership(
                    user_id=viewer_id,
                    organization_id=organization_id,
                    role="viewer",
                ),
                Customer(
                    id=customer_id,
                    organization_id=organization_id,
                    name="Test customer",
                    email=f"{customer_id}@example.com",
                ),
            ]
        )
        await db_session.flush()

        db_session.add(
            Invoice(
                id=invoice_id,
                organization_id=organization_id,
                customer_id=customer_id,
                description="PSP integration test",
                amount_minor=10_000,
                currency="RUB",
                status="issued",
            )
        )
        await db_session.commit()

        yield SimpleNamespace(
            owner_id=owner_id,
            viewer_id=viewer_id,
            outsider_id=outsider_id,
            organization_id=organization_id,
            invoice_id=invoice_id,
        )
    finally:
        await db_session.rollback()

        # Удаляем только данные этой фикстуры, учитывая внешние ключи.
        await db_session.execute(
            delete(Payment).where(
                Payment.organization_id == organization_id
            )
        )
        await db_session.execute(
            delete(Invoice).where(Invoice.id == invoice_id)
        )
        await db_session.execute(
            delete(Customer).where(Customer.id == customer_id)
        )
        await db_session.execute(
            delete(Membership).where(
                Membership.organization_id == organization_id
            )
        )
        await db_session.execute(
            delete(Organization).where(
                Organization.id == organization_id
            )
        )
        await db_session.execute(
            delete(User).where(
                User.id.in_([owner_id, viewer_id, outsider_id])
            )
        )
        await db_session.commit()


@pytest.fixture
def psp_client():
    provider_id = uuid4()

    async def create_transaction(
        external_payment_id,
        amount_minor,
        currency,
    ):
        return SimpleNamespace(
            id=provider_id,
            external_payment_id=external_payment_id,
            amount_minor=amount_minor,
            currency=currency,
            status="pending",
        )

    return SimpleNamespace(
        create_transaction=AsyncMock(side_effect=create_transaction),
        provider_id=provider_id,
    )


@pytest_asyncio.fixture
async def pending_payment_id(db_session, payment_case):
    payment_id = uuid4()
    db_session.add(
        Payment(
            id=payment_id,
            organization_id=payment_case.organization_id,
            invoice_id=payment_case.invoice_id,
            amount_minor=10_000,
            currency="RUB",
            status="pending",
            provider_transaction_id=None,
        )
    )
    await db_session.commit()
    return payment_id


@pytest.mark.asyncio
async def test_create_saves_provider_transaction_id(
    db_session,
    payment_case,
    psp_client,
):
    service = PaymentService(
        session=db_session,
        psp_client=psp_client,
    )

    payment = await service.create(
        actor_id=payment_case.owner_id,
        organization_id=payment_case.organization_id,
        data=PaymentCreate(invoice_id=payment_case.invoice_id),
    )

    assert payment.status == "pending"
    assert payment.provider_transaction_id == psp_client.provider_id

    psp_client.create_transaction.assert_awaited_once_with(
        external_payment_id=payment.id,
        amount_minor=10_000,
        currency="RUB",
    )

    # Перечитываем из БД: проверяем сохранение, а не только объект Python.
    await db_session.refresh(payment)
    assert payment.provider_transaction_id == psp_client.provider_id


@pytest.mark.asyncio
async def test_create_keeps_pending_payment_when_psp_unavailable(
    db_session,
    payment_case,
    psp_client,
):
    psp_client.create_transaction.side_effect = PSPUnavailableError(
        "PSP недоступен"
    )
    service = PaymentService(
        session=db_session,
        psp_client=psp_client,
    )

    with pytest.raises(PSPUnavailableError):
        await service.create(
            actor_id=payment_case.owner_id,
            organization_id=payment_case.organization_id,
            data=PaymentCreate(invoice_id=payment_case.invoice_id),
        )

    # Откат не должен удалить платёж: первая транзакция уже завершена.
    await db_session.rollback()

    result = await db_session.execute(
        select(Payment).where(
            Payment.invoice_id == payment_case.invoice_id,
            Payment.organization_id == payment_case.organization_id,
        )
    )
    payment = result.scalar_one()

    assert payment.status == "pending"
    assert payment.provider_transaction_id is None


@pytest.mark.asyncio
async def test_retry_restores_link_without_creating_another_payment(
    db_session,
    payment_case,
    pending_payment_id,
    psp_client,
):
    service = PaymentService(
        session=db_session,
        psp_client=psp_client,
    )

    payment = await service.retry(
        actor_id=payment_case.owner_id,
        organization_id=payment_case.organization_id,
        payment_id=pending_payment_id,
    )

    assert payment.id == pending_payment_id
    assert payment.status == "pending"
    assert payment.provider_transaction_id == psp_client.provider_id

    psp_client.create_transaction.assert_awaited_once_with(
        external_payment_id=pending_payment_id,
        amount_minor=10_000,
        currency="RUB",
    )

    await db_session.refresh(payment)
    assert payment.provider_transaction_id == psp_client.provider_id

    result = await db_session.execute(
        select(Payment.id).where(
            Payment.invoice_id == payment_case.invoice_id
        )
    )
    assert list(result.scalars()) == [pending_payment_id]


@pytest.mark.asyncio
async def test_repeated_retry_does_not_call_psp_again(
    db_session,
    payment_case,
    pending_payment_id,
    psp_client,
):
    service = PaymentService(
        session=db_session,
        psp_client=psp_client,
    )
    arguments = {
        "actor_id": payment_case.owner_id,
        "organization_id": payment_case.organization_id,
        "payment_id": pending_payment_id,
    }

    first = await service.retry(**arguments)
    provider_id = first.provider_transaction_id

    second = await service.retry(**arguments)

    assert second.id == pending_payment_id
    assert second.provider_transaction_id == provider_id
    assert second.status == "pending"
    psp_client.create_transaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_keeps_pending_when_psp_unavailable(
    db_session,
    payment_case,
    pending_payment_id,
    psp_client,
):
    psp_client.create_transaction.side_effect = PSPUnavailableError(
        "PSP недоступен"
    )
    service = PaymentService(
        session=db_session,
        psp_client=psp_client,
    )

    with pytest.raises(PSPUnavailableError):
        await service.retry(
            actor_id=payment_case.owner_id,
            organization_id=payment_case.organization_id,
            payment_id=pending_payment_id,
        )

    await db_session.rollback()
    payment = await db_session.get(Payment, pending_payment_id)

    assert payment is not None
    assert payment.status == "pending"
    assert payment.provider_transaction_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "wrong_field",
    ["external_payment_id", "amount_minor", "currency"],
)
async def test_retry_rejects_mismatched_psp_response(
    db_session,
    payment_case,
    pending_payment_id,
    psp_client,
    wrong_field,
):
    response = {
        "id": psp_client.provider_id,
        "external_payment_id": pending_payment_id,
        "amount_minor": 10_000,
        "currency": "RUB",
        "status": "pending",
    }
    wrong_values = {
        "external_payment_id": uuid4(),
        "amount_minor": 20_000,
        "currency": "USD",
    }
    response[wrong_field] = wrong_values[wrong_field]

    psp_client.create_transaction.side_effect = None
    psp_client.create_transaction.return_value = SimpleNamespace(**response)

    service = PaymentService(
        session=db_session,
        psp_client=psp_client,
    )

    with pytest.raises(PSPInvalidResponseError):
        await service.retry(
            actor_id=payment_case.owner_id,
            organization_id=payment_case.organization_id,
            payment_id=pending_payment_id,
        )

    await db_session.rollback()
    payment = await db_session.get(Payment, pending_payment_id)

    assert payment is not None
    assert payment.provider_transaction_id is None
    assert payment.status == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actor_field", "expected_error"),
    [
        ("viewer_id", PermissionDeniedError),
        ("outsider_id", OrganizationNotFoundError),
    ],
)
async def test_retry_denies_access_without_calling_psp(
    db_session,
    payment_case,
    pending_payment_id,
    psp_client,
    actor_field,
    expected_error,
):
    service = PaymentService(
        session=db_session,
        psp_client=psp_client,
    )

    with pytest.raises(expected_error):
        await service.retry(
            actor_id=getattr(payment_case, actor_field),
            organization_id=payment_case.organization_id,
            payment_id=pending_payment_id,
        )

    psp_client.create_transaction.assert_not_awaited()
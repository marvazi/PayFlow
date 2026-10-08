import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from psp.core.exceptions import (
    IdempotencyConflictError,
    InvalidTransactionStatusError,
)
from psp.models import Transaction
from psp.schemas.transaction import TransactionCreate
from psp.services.transaction import TransactionService

pytestmark = pytest.mark.asyncio


async def run_concurrently(*operations):
    tasks = [asyncio.create_task(operation) for operation in operations]

    try:
        return await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=15,
        )
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)


async def read_transactions(session_factory, external_payment_id):
    async with session_factory() as session:
        result = await session.execute(
            select(Transaction).where(
                Transaction.external_payment_id == external_payment_id
            )
        )
        return list(result.scalars().all())


async def create_with_barrier(session_factory, data, barrier):
    async with session_factory() as session:
        service = TransactionService(session)
        original_create = service.transaction_repository.create

        async def synchronized_create(*args, **kwargs):
            # Оба запроса уже проверили отсутствие транзакции.
            # Теперь разрешаем им одновременно попытаться создать её.
            await barrier.wait()
            return await original_create(*args, **kwargs)

        service.transaction_repository.create = synchronized_create

        return await service.create(data=data)


async def complete_with_barrier(
    session_factory,
    transaction_id,
    status,
    barrier,
):
    async with session_factory() as session:
        service = TransactionService(session)
        original_get = service.transaction_repository.get_for_update

        async def synchronized_get(*args, **kwargs):
            # Оба запроса готовы получить блокировку одной строки.
            await barrier.wait()
            return await original_get(*args, **kwargs)

        service.transaction_repository.get_for_update = synchronized_get

        return await service.complete(
            transaction_id=transaction_id,
            status=status,
        )


async def seed_transaction(session_factory, external_payment_id):
    async with session_factory() as session:
        service = TransactionService(session)
        transaction = await service.create(
            data=TransactionCreate(
                external_payment_id=external_payment_id,
                amount_minor=10_000,
                currency="RUB",
            )
        )
        return transaction.id


async def test_concurrent_create_same_parameters(
    psp_session_factory,
    tracked_payment_ids,
):
    external_payment_id = uuid4()
    tracked_payment_ids.append(external_payment_id)

    data = TransactionCreate(
        external_payment_id=external_payment_id,
        amount_minor=10_000,
        currency="RUB",
    )
    barrier = asyncio.Barrier(2)

    results = await run_concurrently(
        create_with_barrier(psp_session_factory, data, barrier),
        create_with_barrier(psp_session_factory, data, barrier),
    )

    assert all(isinstance(item, Transaction) for item in results), results
    assert results[0].id == results[1].id

    transactions = await read_transactions(
        psp_session_factory,
        external_payment_id,
    )

    assert len(transactions) == 1
    assert transactions[0].id == results[0].id
    assert transactions[0].amount_minor == 10_000
    assert transactions[0].currency == "RUB"
    assert transactions[0].status == "pending"


async def test_concurrent_create_different_parameters(
    psp_session_factory,
    tracked_payment_ids,
):
    external_payment_id = uuid4()
    tracked_payment_ids.append(external_payment_id)

    amounts = (10_000, 20_000)
    barrier = asyncio.Barrier(2)

    results = await run_concurrently(
        *(
            create_with_barrier(
                psp_session_factory,
                TransactionCreate(
                    external_payment_id=external_payment_id,
                    amount_minor=amount,
                    currency="RUB",
                ),
                barrier,
            )
            for amount in amounts
        )
    )

    successes = [item for item in results if isinstance(item, Transaction)]
    conflicts = [item for item in results if isinstance(item, IdempotencyConflictError)]

    assert len(successes) == 1, results
    assert len(conflicts) == 1, results

    transactions = await read_transactions(
        psp_session_factory,
        external_payment_id,
    )

    assert len(transactions) == 1
    assert transactions[0].id == successes[0].id
    assert transactions[0].amount_minor == successes[0].amount_minor
    assert transactions[0].status == "pending"

    # Сохранилась сумма именно того запроса, который завершился успешно.
    for amount, result in zip(amounts, results):
        if isinstance(result, Transaction):
            assert transactions[0].amount_minor == amount


@pytest.mark.parametrize("status", ["succeeded", "failed"])
async def test_concurrent_complete_same_status(
    psp_session_factory,
    tracked_payment_ids,
    status,
):
    external_payment_id = uuid4()
    tracked_payment_ids.append(external_payment_id)

    transaction_id = await seed_transaction(
        psp_session_factory,
        external_payment_id,
    )
    barrier = asyncio.Barrier(2)

    results = await run_concurrently(
        complete_with_barrier(
            psp_session_factory,
            transaction_id,
            status,
            barrier,
        ),
        complete_with_barrier(
            psp_session_factory,
            transaction_id,
            status,
            barrier,
        ),
    )

    assert all(isinstance(item, Transaction) for item in results), results
    assert all(item.id == transaction_id for item in results)
    assert all(item.status == status for item in results)

    transactions = await read_transactions(
        psp_session_factory,
        external_payment_id,
    )

    assert len(transactions) == 1
    assert transactions[0].status == status
    assert transactions[0].amount_minor == 10_000


async def test_concurrent_complete_conflicting_statuses(
    psp_session_factory,
    tracked_payment_ids,
):
    external_payment_id = uuid4()
    tracked_payment_ids.append(external_payment_id)

    transaction_id = await seed_transaction(
        psp_session_factory,
        external_payment_id,
    )
    statuses = ("succeeded", "failed")
    barrier = asyncio.Barrier(2)

    results = await run_concurrently(
        *(
            complete_with_barrier(
                psp_session_factory,
                transaction_id,
                status,
                barrier,
            )
            for status in statuses
        )
    )

    successes = [item for item in results if isinstance(item, Transaction)]
    conflicts = [
        item for item in results if isinstance(item, InvalidTransactionStatusError)
    ]

    assert len(successes) == 1, results
    assert len(conflicts) == 1, results

    transactions = await read_transactions(
        psp_session_factory,
        external_payment_id,
    )

    assert len(transactions) == 1
    assert transactions[0].status == successes[0].status
    assert transactions[0].amount_minor == 10_000

    for requested_status, result in zip(statuses, results):
        if isinstance(result, Transaction):
            assert transactions[0].status == requested_status

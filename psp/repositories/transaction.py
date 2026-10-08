from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from psp.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        external_payment_id: UUID,
        currency: str,
        amount_minor: int,
    ) -> Transaction:
        transaction = Transaction(
            external_payment_id=external_payment_id,
            currency=currency,
            amount_minor=amount_minor,
            status="pending",
        )
        self.session.add(transaction)
        await self.session.flush()
        return transaction

    async def get(self, transaction_id: UUID) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def get_by_external_payment_id(
        self, external_payment_id: UUID
    ) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(
                Transaction.external_payment_id == external_payment_id
            )
        )
        return result.scalar_one_or_none()

    async def get_for_update(self, transaction_id: UUID) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, status: str, transaction: Transaction
    ) -> Transaction | None:
        transaction.status = status
        await self.session.flush()
        await self.session.refresh(transaction)
        return transaction

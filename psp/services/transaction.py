from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from psp.core.exceptions import IdempotencyConflictError, InvalidTransactionStatusError
from psp.core.exceptions import TransactionNotFoundError
from psp.models import Transaction
from psp.repositories.transaction import TransactionRepository
from psp.schemas.transaction import TransactionCreate




class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.transaction_repository = TransactionRepository(session)

    @staticmethod
    def _check_parameters(
        transaction: Transaction,
        data: TransactionCreate,
    ) -> None:
        if (
            transaction.amount_minor != data.amount_minor
            or transaction.currency != data.currency
        ):
            raise IdempotencyConflictError(
                "Операция с таким external_payment_id "
                "уже существует с другими параметрами"
            )

    async def create(self, data: TransactionCreate) -> Transaction:
        try:
            async with self.session.begin():
                transaction = (
                    await self.transaction_repository.get_by_external_payment_id(
                        external_payment_id=data.external_payment_id,
                    )
                )

                if transaction is not None:
                    self._check_parameters(transaction, data)
                    return transaction

                return await self.transaction_repository.create(
                    external_payment_id=data.external_payment_id,
                    currency=data.currency,
                    amount_minor=data.amount_minor,
                )

        except IntegrityError as exc:
            cause = exc.orig.__cause__

            if not (
                getattr(cause, "sqlstate", None) == "23505"
                and getattr(cause, "constraint_name", None)
                == "transactions_external_payment_id_key"
            ):
                raise

            async with self.session.begin():
                transaction = (
                    await self.transaction_repository.get_by_external_payment_id(
                        external_payment_id=data.external_payment_id,
                    )
                )

                if transaction is None:
                    raise

                self._check_parameters(transaction, data)
                return transaction

    async def get(self, transaction_id: UUID)->Transaction:
        transaction = await self.transaction_repository.get(
            transaction_id=transaction_id
        )
        if transaction is None:
            raise  TransactionNotFoundError("Операция не найдена")
        return transaction

    async def get_by_external_payment_id(self,external_payment_id:UUID):
        transaction = await self.transaction_repository.get_by_external_payment_id(
            external_payment_id=external_payment_id
        )
        if transaction is None:
            raise TransactionNotFoundError("Операция не найдена")
        return transaction

    async def complete(self, transaction_id: UUID,status:str)->Transaction:
        if status not in ("succeeded","failed"):
            raise InvalidTransactionStatusError
        async with self.session.begin():
            transaction = await self.transaction_repository.get_for_update(
                transaction_id=transaction_id
            )
            if transaction is None:
                raise TransactionNotFoundError
            if transaction.status == status:
                return transaction
            if transaction.status != "pending":
                raise InvalidTransactionStatusError
            await self.transaction_repository.update_status(
                status=status,
                transaction=transaction,
            )
        return transaction

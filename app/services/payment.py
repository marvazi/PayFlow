from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exeptions import CustomerNotFoundError, OrganizationNotFoundError, PermissionDeniedError, \
    CustomerAlreadyExistsError, InvoiceNotFoundError, InvoiceNotEditableError, InvalidInvoiceStatusError, \
    PaymentNotFoundError, PaymentAlreadyPendingError, InvalidPaymentStatusError
from app.models import Customer, Invoice, Payment
from app.repositories.customer import CustomerRepository
from app.repositories.invoice import InvoiceRepository
from app.repositories.membership import MembershipRepository
from app.repositories.payment import PaymentRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate
from app.schemas.payment import PaymentCreate





class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.membership_repository = MembershipRepository(session)
        self.invoice_repository = InvoiceRepository(session)
        self.payment_repository = PaymentRepository(session)

    async def create(self,actor_id:UUID,organization_id:UUID, data: PaymentCreate) -> Payment:
        try:
            async with self.session.begin():
                membership = await self.membership_repository.get_by_user_and_organization(actor_id, organization_id)
                if membership is None:
                    raise OrganizationNotFoundError("Организация не найдена")
                if membership.role not in ('manager', 'owner'):
                    raise PermissionDeniedError("Недостаточно прав")
                invoice = await self.invoice_repository.get_for_update(
                    invoice_id=data.invoice_id,
                    organization_id=organization_id
                )
                if invoice is None:
                    raise InvoiceNotFoundError("Нет такого счета")
                if invoice.status != "issued":
                    raise InvalidInvoiceStatusError(
                        "Оплатить можно только выставленный счёт"
                    )
                pending_payment = await self.payment_repository.get_pending_by_invoice(
                    invoice_id=invoice.id,
                    organization_id=organization_id
                )
                if pending_payment is not None:
                    raise PaymentAlreadyPendingError("Для этого счёта уже есть незавершённый платёж")

                created_payment = await self.payment_repository.create(
                    invoice_id=data.invoice_id,
                    amount_minor=invoice.amount_minor,
                    currency=invoice.currency,
                    organization_id=organization_id,
                )
        except IntegrityError as exc:
            cause = exc.orig.__cause__

            if (
                    getattr(cause, "sqlstate", None) == "23505"
                    and getattr(cause, "constraint_name", None)
                    == "payments_one_pending_per_invoice_idx"
            ):
                raise PaymentAlreadyPendingError(
                    "Для этого счёта уже есть незавершённый платёж"
                ) from exc

            raise
        return created_payment

    async def get_payment(self,actor_id:UUID,organization_id:UUID,payment_id:UUID) -> Payment:
        membership = await self.membership_repository.get_by_user_and_organization(actor_id, organization_id)
        if membership is None:
            raise OrganizationNotFoundError("Организация не найдена")
        payment = await self.payment_repository.get(
            payment_id=payment_id,
            organization_id=organization_id
        )
        if payment is None:
            raise PaymentNotFoundError("Не удалось найти платеж")
        return payment


    async def list_payments(self,actor_id:UUID,invoice_id:UUID,organization_id:UUID) -> list[Payment]:
        membership = await self.membership_repository.get_by_user_and_organization(
            user_id=actor_id,
            organization_id=organization_id
        )
        if membership is None:
            raise OrganizationNotFoundError("Организация не найдена")
        invoice = await self.invoice_repository.get(
            invoice_id=invoice_id,
            organization_id=organization_id
        )
        if invoice is None:
            raise InvoiceNotFoundError("Нет такого счета")

        payments_list = await self.payment_repository.list_by_invoice(
            invoice_id=invoice_id,
            organization_id=organization_id
        )
        return payments_list

    async def process_result(
            self,
            organization_id:UUID,
            payment_id:UUID,
            status:str,
    )->Payment:
        if status not in ('succeeded', 'failed'):
            raise InvalidPaymentStatusError(
                "Допустимые результаты оплаты: succeeded, failed"
            )
        async with self.session.begin():
            payment = await self.payment_repository.get(
                payment_id=payment_id,
                organization_id=organization_id,
            )
            if payment is None:
                raise PaymentNotFoundError("Платёж не найден")
            invoice = await self.invoice_repository.get_for_update(
                invoice_id=payment.invoice_id,
                organization_id=organization_id,
            )
            if invoice is None:
                raise InvoiceNotFoundError("Счёт не найден")
            payment = await self.payment_repository.get_for_update(
                payment_id=payment_id,
                organization_id=organization_id,
            )
            if payment is None:
                raise PaymentNotFoundError("Платёж не найден")

            if payment.status == status:
                return payment
            if payment.status != "pending":
                raise InvalidPaymentStatusError(
                    "Завершённый платёж нельзя перевести в другой статус"
                )
            if invoice.status != "issued":
                raise InvalidInvoiceStatusError(
                    "Обработать оплату можно только для выставленного счёта"
                )
            if status == "succeeded":
                await self.invoice_repository.update_status(
                    invoice=invoice,
                    status="paid",
                )
            await self.payment_repository.update_status(payment=payment, status=status)

        return payment
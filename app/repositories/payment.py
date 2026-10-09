from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Payment


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, invoice_id: UUID, organization_id: UUID, amount_minor: int, currency: str
    ) -> Payment:
        payment = Payment(
            invoice_id=invoice_id,
            organization_id=organization_id,
            amount_minor=amount_minor,
            currency=currency,
            status="pending",
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get(self, payment_id: UUID, organization_id: UUID) -> Payment | None:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.id == payment_id)
            .where(Payment.organization_id == organization_id)
        )
        payment = result.scalar_one_or_none()
        return payment

    async def list_by_invoice(
        self, invoice_id: UUID, organization_id: UUID
    ) -> list[Payment]:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.invoice_id == invoice_id)
            .where(Payment.organization_id == organization_id)
            .order_by(Payment.created_at, Payment.id)
        )
        return list(result.scalars().all())

    async def get_pending_by_invoice(
        self,
        invoice_id: UUID,
        organization_id: UUID,
    ) -> Payment | None:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.invoice_id == invoice_id)
            .where(Payment.organization_id == organization_id)
            .where(Payment.status == "pending")
        )
        payment = result.scalar_one_or_none()
        return payment

    async def get_for_update(
        self, payment_id: UUID, organization_id: UUID
    ) -> Payment | None:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.id == payment_id)
            .where(Payment.organization_id == organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        payment = result.scalar_one_or_none()
        return payment

    async def update_status(self, payment: Payment, status: str) -> Payment:
        payment.status = status
        await self.session.flush()
        await self.session.refresh(payment)
        return payment

    async def set_provider_transaction_id(self,payment: Payment, provider_transaction_id: UUID,) -> Payment:
        payment.provider_transaction_id = provider_transaction_id
        await self.session.flush()
        await self.session.refresh(payment)
        return payment


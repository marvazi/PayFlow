from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice


class InvoiceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self,customer_id:UUID, organization_id:UUID, description:str, amount_minor:int, currency:str) -> Invoice:
        invoice = Invoice(
            customer_id=customer_id,
            organization_id=organization_id,
            description=description,
            amount_minor=amount_minor,
            currency=currency,
            status="draft"
        )
        self.session.add(invoice)
        await self.session.flush()
        return invoice

    async def get(self,invoice_id:UUID,organization_id:UUID) -> Invoice | None:
        result = await self.session.execute(
            select(Invoice).
            where(Invoice.id == invoice_id).
            where(Invoice.organization_id == organization_id)
            )
        invoice = result.scalar_one_or_none()
        return invoice

    async def list_by_organization(self,organization_id:UUID) -> list[Invoice]:
        result = await self.session.execute(
            select(Invoice).
            where(Invoice.organization_id == organization_id).
            order_by(Invoice.created_at, Invoice.id)
        )
        return list(result.scalars().all())
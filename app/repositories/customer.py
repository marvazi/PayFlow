from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.customer import Customer

class CustomerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find(self, customer_id: UUID,organization_id:UUID) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id)
        )
        customer = result.scalar_one_or_none()
        return customer
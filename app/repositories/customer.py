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

    async def create(self, name:str, email:str, organization_id:UUID) -> Customer:
        customer = Customer(name=name, email=email, organization_id=organization_id)
        self.session.add(customer)
        await self.session.flush()
        return customer

    async def list_by_organization(self, organization_id:UUID) ->list[Customer]:
        res = await self.session.execute(
            select(Customer).
            where(Customer.organization_id == organization_id).
            order_by(Customer.created_at, Customer.id)
        )
        return list(res.scalars().all())

    async def update(self, customer:Customer,changes: dict[str, str]) -> Customer:
        if "name" in changes:
            customer.name = changes["name"]
        if "email" in changes:
            customer.email = changes["email"]
        await self.session.flush()
        return customer
    async def delete(self, customer:Customer) -> None:
        await self.session.delete(customer)
        await self.session.flush()

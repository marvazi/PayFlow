from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exeptions import CustomerNotFoundError
from app.models import Customer
from app.repositories.customer import CustomerRepository


class CustomerService:
    def __init__(self,session: AsyncSession):
        self.session = session
        self.customer_repository = CustomerRepository(session)

    async def find_customer_by_id(self, customer_id:UUID,organization_id: UUID) -> Customer:
        customer = await self.customer_repository.find(customer_id=customer_id, organization_id=organization_id)
        if customer is None:
            raise CustomerNotFoundError("Клиент не найден")
        return customer


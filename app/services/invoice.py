from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exeptions import CustomerNotFoundError, OrganizationNotFoundError, PermissionDeniedError, \
    CustomerAlreadyExistsError, InvoiceNotFoundError
from app.models import Customer, Invoice
from app.repositories.customer import CustomerRepository
from app.repositories.invoice import InvoiceRepository
from app.repositories.membership import MembershipRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.schemas.invoice import InvoiceCreate





class InvoiceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.customer_repository = CustomerRepository(session)
        self.membership_repository = MembershipRepository(session)
        self.invoice_repository = InvoiceRepository(session)

    async def create(self, actor_id:UUID,organization_id:UUID,data: InvoiceCreate) -> Invoice:
        async with self.session.begin():
            membership = await self.membership_repository.get_by_user_and_organization(actor_id,organization_id)
            if membership is None:
                raise OrganizationNotFoundError("Организация не найдена")
            if membership.role not in ('manager', 'owner'):
                raise PermissionDeniedError("Недостаточно прав")
            customer = await self.customer_repository.find(customer_id=data.customer_id,organization_id=organization_id)
            if customer is None:
                raise CustomerNotFoundError("Клиент не найден")
            created_invoice = await self.invoice_repository.create(
                customer_id=data.customer_id,
                organization_id=organization_id,
                description=data.description,
                currency=data.currency,
                amount_minor=data.amount_minor,
            )
        return created_invoice


    async def list_invoices(self,actor_id:UUID,organization_id:UUID) -> list[Invoice]:
        membership = await self.membership_repository.get_by_user_and_organization(user_id=actor_id,organization_id=organization_id)
        if membership is None:
            raise OrganizationNotFoundError("Организация не найдена")
        invoices_list = await self.invoice_repository.list_by_organization(organization_id=organization_id)
        return invoices_list


    async def get_invoice(self,actor_id:UUID,invoice_id:UUID,organization_id:UUID) -> Invoice:
        membership = await self.membership_repository.get_by_user_and_organization(user_id=actor_id,organization_id=organization_id)
        if membership is None:
            raise OrganizationNotFoundError("Организация не найдена")
        invoice = await self.invoice_repository.get(organization_id=organization_id,invoice_id=invoice_id)
        if invoice is None:
            raise InvoiceNotFoundError("Счёт не найден")

        return invoice

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exeptions import CustomerNotFoundError, OrganizationNotFoundError, PermissionDeniedError, \
CustomerAlreadyExistsError
from app.models import Customer
from app.repositories.customer import CustomerRepository
from app.repositories.membership import MembershipRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self,session: AsyncSession):
        self.session = session
        self.customer_repository = CustomerRepository(session)
        self.membership_repository = MembershipRepository(session)

    async def find_customer_by_id(self,actor_id:UUID, customer_id:UUID,organization_id: UUID) -> Customer:
        membership = await self.membership_repository.get_by_user_and_organization(
            user_id=actor_id,
            organization_id=organization_id
        )
        if membership is None:
            raise OrganizationNotFoundError("Организация не найдена")
        customer = await self.customer_repository.find(customer_id=customer_id, organization_id=organization_id)
        if customer is None:
            raise CustomerNotFoundError("Клиент не найден")
        return customer

    async def list_customers(self,actor_id:UUID,organization_id: UUID) -> list[Customer]:
        membership = await self.membership_repository.get_by_user_and_organization(user_id=actor_id, organization_id=organization_id)
        if membership is None:
            raise OrganizationNotFoundError("Организация не найдена")
        customers = await self.customer_repository.list_by_organization(organization_id=organization_id)
        return customers

    async def update_customer(self,actor_id:UUID,organization_id:UUID,data:CustomerUpdate,customer_id:UUID) -> Customer:
        try:
            async with self.session.begin():
                membership = await self.membership_repository.get_by_user_and_organization(
                    user_id=actor_id,
                    organization_id=organization_id
                )
                if membership is None:
                    raise OrganizationNotFoundError("Организация не найдена")
                if membership.role not in ('manager', 'owner'):
                    raise PermissionDeniedError("Недостаточно прав")
                customer = await self.customer_repository.find(customer_id=customer_id, organization_id=organization_id)
                if customer is None:
                    raise CustomerNotFoundError("Клиент не найден")
                changes = data.model_dump(exclude_unset=True)
                await self.customer_repository.update(customer=customer, changes=changes)
        except IntegrityError as exc:
                cause = exc.orig.__cause__

                if (
                        getattr(cause, "sqlstate", None) == "23505"
                        and getattr(cause, "constraint_name", None)
                        == "customers_org_email_unique_idx"
                ):
                    raise CustomerAlreadyExistsError(
                        "Клиент с таким email уже существует в организации"
                    ) from exc

                raise
        return customer

    async def create_customer(self, actor_id:UUID,organization_id:UUID,data:CustomerCreate) -> Customer:
        try:
            async with self.session.begin():
                membership = await self.membership_repository.get_by_user_and_organization(
                    user_id=actor_id,
                    organization_id=organization_id
                )
                if membership is None:
                    raise OrganizationNotFoundError("Организация не найдена")
                if membership.role not in ('manager', 'owner'):
                    raise PermissionDeniedError("Недостаточно прав")
                created_customer = await self.customer_repository.create(
                    email=data.email,
                    name=data.name,
                    organization_id=organization_id
                )
        except IntegrityError as exc:
            cause = exc.orig.__cause__

            if (
                    getattr(cause, "sqlstate", None) == "23505"
                    and getattr(cause, "constraint_name", None)
                    == "customers_org_email_unique_idx"
            ):
                raise CustomerAlreadyExistsError(
                    "Клиент с таким email уже существует в организации"
                ) from exc

            raise
        return created_customer

    async def delete_customer(self,actor_id:UUID,customer_id:UUID,organization_id:UUID) -> None:
        async with self.session.begin():
            membership = await self.membership_repository.get_by_user_and_organization(
                user_id=actor_id,
                organization_id=organization_id
            )
            if membership is None:
                raise OrganizationNotFoundError("Организация не найдена")
            if membership.role not in ('manager', 'owner'):
                raise PermissionDeniedError("Недостаточно прав")
            customer = await self.customer_repository.find(customer_id=customer_id, organization_id=organization_id)
            if customer is None:
                raise CustomerNotFoundError("Клиент не найден")
            await self.customer_repository.delete(customer=customer)






from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import RedisCache
from app.core.exeptions import (
    CustomerAlreadyExistsError,
    CustomerHasInvoicesError,
    CustomerNotFoundError,
    OrganizationNotFoundError,
    PermissionDeniedError,
)
from app.models import Customer
from app.repositories.customer import CustomerRepository
from app.repositories.membership import MembershipRepository
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate


class CustomerService:
    def __init__(self, session: AsyncSession, cache: RedisCache) -> None:
        self.session = session
        self.customer_repository = CustomerRepository(session)
        self.membership_repository = MembershipRepository(session)
        self.cache = cache

    async def find_customer_by_id(
        self, actor_id: UUID, customer_id: UUID, organization_id: UUID
    ) -> Customer:
        membership = await self.membership_repository.get_by_user_and_organization(
            user_id=actor_id, organization_id=organization_id
        )
        if membership is None:
            raise OrganizationNotFoundError("Организация не найдена")
        customer = await self.customer_repository.find(
            customer_id=customer_id, organization_id=organization_id
        )
        if customer is None:
            raise CustomerNotFoundError("Клиент не найден")
        return customer

    async def list_customers(
        self,
        actor_id: UUID,
        organization_id: UUID,
    ) -> list[CustomerResponse]:
        membership = await self.membership_repository.get_by_user_and_organization(
            user_id=actor_id, organization_id=organization_id
        )
        if membership is None:
            raise OrganizationNotFoundError("Организация не найдена")
        key = f"organizations:{organization_id}:customers"
        cached_customers = await self.cache.get(key)
        if cached_customers is not None:
            return [
                CustomerResponse.model_validate(customer)
                for customer in cached_customers
            ]

        customers = await self.customer_repository.list_by_organization(
            organization_id=organization_id,
        )
        result = [CustomerResponse.model_validate(customer) for customer in customers]
        await self.cache.set(
            key,
            [customer.model_dump(mode="json") for customer in result],
        )

        return result

    async def update_customer(
        self,
        actor_id: UUID,
        organization_id: UUID,
        data: CustomerUpdate,
        customer_id: UUID,
    ) -> Customer:
        try:
            async with self.session.begin():
                membership = (
                    await self.membership_repository.get_by_user_and_organization(
                        user_id=actor_id, organization_id=organization_id
                    )
                )
                if membership is None:
                    raise OrganizationNotFoundError("Организация не найдена")
                if membership.role not in ("manager", "owner"):
                    raise PermissionDeniedError("Недостаточно прав")
                customer = await self.customer_repository.find(
                    customer_id=customer_id, organization_id=organization_id
                )
                if customer is None:
                    raise CustomerNotFoundError("Клиент не найден")
                changes = data.model_dump(exclude_unset=True)
                await self.customer_repository.update(
                    customer=customer, changes=changes
                )
        except IntegrityError as exc:
            cause = exc.orig.__cause__  # type: ignore[union-attr]

            if (
                getattr(cause, "sqlstate", None) == "23505"
                and getattr(cause, "constraint_name", None)
                == "customers_org_email_unique_idx"
            ):
                raise CustomerAlreadyExistsError(
                    "Клиент с таким email уже существует в организации"
                ) from exc

            raise
        await self.cache.delete(f"organizations:{organization_id}:customers")
        return customer

    async def create_customer(
        self, actor_id: UUID, organization_id: UUID, data: CustomerCreate
    ) -> Customer:
        try:
            async with self.session.begin():
                membership = (
                    await self.membership_repository.get_by_user_and_organization(
                        user_id=actor_id, organization_id=organization_id
                    )
                )
                if membership is None:
                    raise OrganizationNotFoundError("Организация не найдена")
                if membership.role not in ("manager", "owner"):
                    raise PermissionDeniedError("Недостаточно прав")
                created_customer = await self.customer_repository.create(
                    email=data.email, name=data.name, organization_id=organization_id
                )
        except IntegrityError as exc:
            cause = exc.orig.__cause__  # type: ignore[union-attr]

            if (
                getattr(cause, "sqlstate", None) == "23505"
                and getattr(cause, "constraint_name", None)
                == "customers_org_email_unique_idx"
            ):
                raise CustomerAlreadyExistsError(
                    "Клиент с таким email уже существует в организации"
                ) from exc

            raise
        await self.cache.delete(f"organizations:{organization_id}:customers")
        return created_customer

    async def delete_customer(
        self, actor_id: UUID, customer_id: UUID, organization_id: UUID
    ) -> None:
        try:
            async with self.session.begin():
                membership = (
                    await self.membership_repository.get_by_user_and_organization(
                        user_id=actor_id, organization_id=organization_id
                    )
                )
                if membership is None:
                    raise OrganizationNotFoundError("Организация не найдена")
                if membership.role not in ("manager", "owner"):
                    raise PermissionDeniedError("Недостаточно прав")
                customer = await self.customer_repository.find(
                    customer_id=customer_id, organization_id=organization_id
                )
                if customer is None:
                    raise CustomerNotFoundError("Клиент не найден")
                await self.customer_repository.delete(customer=customer)
        except IntegrityError as exc:
            cause = exc.orig.__cause__  # type: ignore[union-attr]
            if (
                getattr(cause, "sqlstate", None) == "23001"
                and getattr(cause, "constraint_name", None)
                == "invoices_customer_id_fkey"
            ):
                raise CustomerHasInvoicesError(
                    "Нельзя удалить клиента, у которого есть счета"
                ) from exc
            raise
        await self.cache.delete(f"organizations:{organization_id}:customers")

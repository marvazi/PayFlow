from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exeptions import OrganizationNotFoundError
from app.models import Organization
from app.repositories.organization import OrganizationRepository
from app.repositories.membership import MembershipRepository


class OrganizationService:
    def __init__(self, session:AsyncSession):
        self.session = session
        self.organization_repository = OrganizationRepository(session)
        self.membership_repository = MembershipRepository(session)

    async def create(self, name: str, user_id: UUID) -> Organization:
        async with self.session.begin():
            organization = await self.organization_repository.create(name=name)
            await self.membership_repository.create(
                user_id=user_id,
                organization_id=organization.id,
                role="owner",
            )

        return organization

    async def get_by_user_id(self, user_id: UUID) -> list[Organization]:
        res = await self.organization_repository.get_by_user_id(user_id=user_id)
        return res

    async def get_organization_by_id(self, organization_id: UUID,user_id:UUID) -> Organization :
        res = await self.organization_repository.get_one_by_id(organization_id=organization_id, user_id=user_id)
        if res is None:
            raise OrganizationNotFoundError("Organization not found")
        return res




from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, Membership, organization
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

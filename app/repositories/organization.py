from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Membership
from app.models.organization import Organization
from app.schemas.organization import OrganizationResponse


class OrganizationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name:str) -> Organization:
        organization = Organization(name=name)
        self.session.add(organization)
        await self.session.flush()
        return organization

    async def get_by_user_id(self, user_id:UUID) -> list[Organization]:
        result = await self.session.execute(
            select(Organization).
            join(Membership,Organization.id == Membership.organization_id).
            where(Membership.user_id == user_id).
            order_by(Organization.created_at, Organization.id)
        )
        return list(result.scalars().all())

    async def get_one_by_id(self, organization_id:UUID, user_id:UUID) -> Organization | None:
        result = await self.session.execute(
            select(Organization).
            join(Membership, Organization.id == Membership.organization_id).
            where(
                Membership.user_id == user_id,
                Organization.id == organization_id
            )
        )
        return result.scalar_one_or_none()
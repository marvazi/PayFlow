from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Membership, Organization


class MembershipRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id:UUID,
        organization_id:UUID,
        role:str,
    ) -> Membership:
        membership = Membership(user_id=user_id, organization_id=organization_id, role=role)
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def get_by_user_and_organization(self, user_id:UUID,organization_id:UUID) -> Membership | None:
        result = await self.session.execute(
            select(Membership).
            where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_users_by_organization(self, organization_id:UUID) -> list[Membership]:
        result = await self.session.execute(
            select(Membership).
            where(
                Membership.organization_id == organization_id,
            )
        )
        return list(result.scalars().all())

    async def update_role(self,role:str,membership:Membership) -> Membership:
        membership.role = role
        await self.session.flush()
        return membership

    async def delete(self,membership:Membership) -> None:
        await self.session.delete(membership)
        await self.session.flush()
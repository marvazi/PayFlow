from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Membership


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
    
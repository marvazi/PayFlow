from uuid import UUID
from app.core.exeptions import PermissionDeniedError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exeptions import OrganizationNotFoundError
from app.models import  Membership
from app.repositories.membership import MembershipRepository


class MembershipService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.membership_repository = MembershipRepository(session)

    async def require_owner(self, user_id: UUID, organization_id: UUID) -> Membership:
        membership = await self.membership_repository.get_by_user_and_organization(user_id=user_id, organization_id=organization_id)
        if membership is None:
            raise OrganizationNotFoundError("Организация не найдена")
        elif membership and membership.role != 'owner':
            raise PermissionDeniedError("Недостаточно прав")
        return membership


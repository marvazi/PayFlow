from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.exeptions import PermissionDeniedError, UserNotFoundError, EmailAlreadyExistsError, \
    MembershipAlreadyExistsError, InvalidMembershipRoleError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exeptions import OrganizationNotFoundError
from app.models import Membership, User
from app.repositories.membership import MembershipRepository
from app.repositories.user import UserRepository




class MembershipService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.membership_repository = MembershipRepository(session)
        self.user_repository = UserRepository(session)

    async def require_owner(self, user_id: UUID, organization_id: UUID) -> Membership:
        membership = await self.membership_repository.get_by_user_and_organization(user_id=user_id, organization_id=organization_id)
        if membership is None:
            raise OrganizationNotFoundError("Организация не найдена")
        elif membership and membership.role != 'owner':
            raise PermissionDeniedError("Недостаточно прав")
        return membership
    async def add_member(
            self,
            actor_id: UUID,
            organization_id: UUID,
            new_user_id: UUID,
            role:str,
    ) -> Membership:
        if role not in('manager',"viewer"):
            raise InvalidMembershipRoleError('Допустимые роли: manager, viewer')
        try:
            async with self.session.begin():
                await self.require_owner(user_id=actor_id, organization_id=organization_id)
                user = await self.user_repository.get_by_id(user_id=new_user_id)
                if user is None:
                    raise UserNotFoundError("Пользователь не найден")
                membership = await self.membership_repository.create(
                    user_id=new_user_id,
                    organization_id=organization_id,
                    role=role,
                )
        except IntegrityError as exc:
            cause = exc.orig.__cause__

            if (
                    getattr(cause, "sqlstate", None) == "23505"
                    and getattr(cause, "constraint_name", None)
                    == "memberships_user_org_unique"
            ):
                raise MembershipAlreadyExistsError(
                    "Пользователь уже состоит в организации"
                ) from exc

            raise
        return membership




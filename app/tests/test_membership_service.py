from uuid import uuid4

import pytest
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from app.core.exeptions import PermissionDeniedError, MembershipAlreadyExistsError
from app.models.user import User
from app.models import Organization, Membership
from app.services.membership import MembershipService
from app.services.organization import OrganizationService


@pytest.mark.asyncio
async def test_create_membership(db_session):
    owner_email = f"{uuid4()}@example.com"
    new_user_email = f"{uuid4()}@example.com"
    organization_name = f"Test-{uuid4()}"

    try:
        owner = User(
            email=owner_email,
            name="Владелец",
            password_hash=None,
        )
        new_user = User(
            email=new_user_email,
            name="Новый участник",
            password_hash=None,
        )
        db_session.add_all([owner, new_user])
        await db_session.commit()

        organization_service = OrganizationService(db_session)
        organization = await organization_service.create(
            user_id=owner.id,
            name=organization_name,
        )

        membership_service = MembershipService(db_session)
        member = await membership_service.add_member(
            actor_id=owner.id,
            organization_id=organization.id,
            new_user_id=new_user.id,
            role="manager",
        )

        result = await db_session.execute(
            select(Membership).where(
                Membership.user_id == new_user.id,
                Membership.organization_id == organization.id,
            )
        )
        saved_membership = result.scalar_one_or_none()

        assert saved_membership is not None
        assert saved_membership.role == "manager"
        assert saved_membership.id == member.id

    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(Organization).where(
                Organization.name == organization_name
            )
        )
        await db_session.execute(
            delete(User).where(
                User.email.in_([owner_email, new_user_email])
            )
        )
        await db_session.commit()

@pytest.mark.asyncio
async def test_manager_cannot_add_member(db_session):
    owner_email = f"{uuid4()}@example.com"
    manager_email = f"{uuid4()}@example.com"
    new_user_email = f"{uuid4()}@example.com"
    organization_name = f"Test-{uuid4()}"

    try:
        owner = User(
            email=owner_email,
            name="Владелец",
            password_hash=None,
        )
        manager = User(
            email=manager_email,
            name="Менеджер",
            password_hash=None,
        )
        new_user = User(
            email=new_user_email,
            name="Новый участник",
            password_hash=None,
        )
        db_session.add_all([owner, manager, new_user])
        await db_session.commit()

        owner_id = owner.id
        manager_id = manager.id
        new_user_id = new_user.id

        organization_service = OrganizationService(db_session)
        organization = await organization_service.create(
            user_id=owner_id,
            name=organization_name,
        )
        organization_id = organization.id

        membership_service = MembershipService(db_session)
        await membership_service.add_member(
            actor_id=owner_id,
            organization_id=organization_id,
            new_user_id=manager_id,
            role="manager",
        )

        with pytest.raises(PermissionDeniedError):
            await membership_service.add_member(
                actor_id=manager_id,
                organization_id=organization_id,
                new_user_id=new_user_id,
                role="viewer",
            )

        result = await db_session.execute(
            select(Membership).where(
                Membership.user_id == new_user_id,
                Membership.organization_id == organization_id,
            )
        )
        assert result.scalar_one_or_none() is None

    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(Organization).where(
                Organization.name == organization_name
            )
        )
        await db_session.execute(
            delete(User).where(
                User.email.in_([
                    owner_email,
                    manager_email,
                    new_user_email,
                ])
            )
        )
        await db_session.commit()

@pytest.mark.asyncio
async def test_duplicate_membership_preserves_existing_role(db_session):
    owner_email = f"{uuid4()}@example.com"
    member_email = f"{uuid4()}@example.com"
    organization_name = f"Test-{uuid4()}"

    try:
        owner = User(
            email=owner_email,
            name="Владелец",
            password_hash=None,
        )
        new_user = User(
            email=member_email,
            name="Участник",
            password_hash=None,
        )
        db_session.add_all([owner, new_user])
        await db_session.commit()

        owner_id = owner.id
        member_user_id = new_user.id

        organization_service = OrganizationService(db_session)
        organization = await organization_service.create(
            user_id=owner_id,
            name=organization_name,
        )
        organization_id = organization.id

        membership_service = MembershipService(db_session)
        membership = await membership_service.add_member(
            actor_id=owner_id,
            organization_id=organization_id,
            new_user_id=member_user_id,
            role="manager",
        )
        membership_id = membership.id

        with pytest.raises(MembershipAlreadyExistsError):
            await membership_service.add_member(
                actor_id=owner_id,
                organization_id=organization_id,
                new_user_id=member_user_id,
                role="viewer",
            )

        result = await db_session.execute(
            select(Membership).where(
                Membership.user_id == member_user_id,
                Membership.organization_id == organization_id,
            )
        )
        memberships = result.scalars().all()

        assert len(memberships) == 1
        assert memberships[0].id == membership_id
        assert memberships[0].role == "manager"

    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(Organization).where(
                Organization.name == organization_name
            )
        )
        await db_session.execute(
            delete(User).where(
                User.email.in_([owner_email, member_email])
            )
        )
        await db_session.commit()
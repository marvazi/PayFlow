from uuid import uuid4

import pytest
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.models import Organization, Membership
from app.services.organization import OrganizationService



@pytest.mark.asyncio
async def test_create_organization_rolls_back_for_missing_user(db_session) :
    service = OrganizationService(db_session)
    name = f"Test-{uuid4()}"
    with pytest.raises(IntegrityError):
        await service.create(user_id = uuid4(),name =name)

    result = await db_session.execute(
        select(Organization).where(Organization.name == name)
    )
    assert result.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_create_organization_with_owner(db_session):

    user = User(
        email=f"{uuid4()}@example.com",
        name=f"Test-{uuid4()}",
        password_hash=None
    )
    db_session.add(user)
    await db_session.commit()

    user_id = user.id
    org_name = f"Test-{uuid4()}"

    try:

        service = OrganizationService(db_session)
        organization = await service.create(user_id=user.id, name=org_name)
        org_res = await db_session.execute(
            select(Organization).where(Organization.id == organization.id)
        )
        saved_organization = org_res.scalar_one_or_none()
        assert saved_organization is not None
        assert saved_organization.name == org_name

        membership_res = await db_session.execute(
            select(Membership).where(
                Membership.organization_id == organization.id
            )
        )
        membership = membership_res.scalar_one_or_none()

        assert membership is not None
        assert membership.user_id == user.id
        assert membership.role == "owner"
    finally:
        await db_session.rollback()

        await db_session.execute(
            delete(Organization).where(Organization.name == org_name)
        )
        await db_session.execute(
            delete(User).where(User.id == user_id)
        )
        await db_session.commit()
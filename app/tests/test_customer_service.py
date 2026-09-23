from uuid import uuid4
import pytest
from app.models import Organization, Customer, Membership
from app.services.customer import CustomerService
from app.models.user import User

@pytest.mark.asyncio
async def test_find_customer_in_organization(db_session):
    try:
        user = User(
            name="Test user",
            email=f"{uuid4()}@example.com",
            password_hash=None,
        )
        organization = Organization(name=f"Test-{uuid4()}")

        db_session.add_all([user, organization])
        await db_session.flush()

        membership = Membership(
            user_id=user.id,
            organization_id=organization.id,
            role="viewer",
        )
        customer = Customer(
            email=f"{uuid4()}@example.com",
            name="Max",
            organization_id=organization.id,
        )

        db_session.add_all([membership, customer])
        await db_session.flush()

        service = CustomerService(db_session)
        found_customer = await service.find_customer_by_id(
            actor_id=user.id,
            organization_id=organization.id,
            customer_id=customer.id,
        )

        assert found_customer.id == customer.id
        assert found_customer.organization_id == organization.id
        assert found_customer.name == "Max"
        assert found_customer.email == customer.email

    finally:
        await db_session.rollback()


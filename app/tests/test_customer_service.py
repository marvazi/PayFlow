from uuid import uuid4
import pytest
from app.models import Organization, Customer
from app.services.customer import CustomerService



@pytest.mark.asyncio
async def test_find_customer_in_organization(db_session):
    organization = Organization(name=f"Test-{uuid4()}")
    db_session.add(organization)
    await db_session.flush()
    customer = Customer(email="asad@asd.com", name="Max", organization_id=organization.id)
    db_session.add(customer)
    await db_session.flush()
    service = CustomerService(db_session)
    found_customer = await service.find_customer_by_id(
        organization_id=organization.id,
        customer_id=customer.id
    )
    assert found_customer == customer



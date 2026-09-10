from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization


class OrganizationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name:str) -> Organization:
        organization = Organization(name=name)
        self.session.add(organization)
        await self.session.flush()
        return organization
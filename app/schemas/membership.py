from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MembershipCreate(BaseModel):
    user_id: UUID
    role: Literal["manager", "viewer"]

class MembershipResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: Literal["owner","manager", "viewer"]
    created_at: datetime

class MembershipUpdate(BaseModel):

    role: Literal["manager", "viewer"]
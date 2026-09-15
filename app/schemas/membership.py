from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MembershipCreate(BaseModel):
    user_id: UUID
    role: Literal["manager", "viewer"]
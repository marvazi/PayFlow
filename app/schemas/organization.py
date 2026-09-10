from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(max_length=255, min_length=1)

class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:UUID
    name:str
    created_at:datetime


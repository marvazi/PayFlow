from typing import Literal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator

class CustomerCreate(BaseModel):
    name: str = Field(max_length=255, min_length=1)
    email: EmailStr

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:UUID
    email:EmailStr
    name:str
    created_at:datetime
    organization_id: UUID

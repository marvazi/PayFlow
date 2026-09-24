from uuid import UUID
from datetime import datetime
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
    model_validator,
ConfigDict
)
from typing import Self
from typing import Literal

from sqlalchemy import BIGINT


class InvoiceCreate(BaseModel):
    customer_id: UUID
    description: str = Field(min_length=1, max_length=500)
    amount_minor: int = Field(strict=True, gt=0)
    currency: Literal["RUB"] = "RUB"

    @field_validator("description", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:UUID
    organization_id:UUID
    customer_id:UUID
    description: str
    currency:str
    status:str
    amount_minor:int
    created_at:datetime


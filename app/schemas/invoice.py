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

class InvoiceUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    description: str | None = Field(default=None,min_length=1, max_length=500)
    amount_minor:int | None = Field(default=None,strict=True,gt=0,le=9_223_372_036_854_775_807)

    @field_validator("amount_minor", mode="before")
    @classmethod
    def strip_amount(cls, value: object) -> object:
        if value is None:
            raise ValueError("Передайте хотя бы одно поле: description или amount_minor")
        if isinstance(value, str):
            return value
        return value

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        if value is None:
            raise ValueError("Передайте хотя бы одно поле: description или amount_minor")
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def check_has_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Передайте хотя бы одно поле: description или amount_minor")
        return self
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


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


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: UUID

class PaymentResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )
    id: UUID
    organization_id: UUID
    invoice_id: UUID
    currency: Literal["RUB"]
    status: Literal["pending", "succeeded", "failed"]
    amount_minor: int
    created_at: datetime
    updated_at: datetime

class PaymentUpdate(BaseModel):
    pass
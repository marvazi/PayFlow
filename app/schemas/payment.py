from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
)


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: UUID


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    invoice_id: UUID
    currency: Literal["RUB"]
    status: Literal["pending", "succeeded", "failed"]
    amount_minor: int
    created_at: datetime
    updated_at: datetime
    provider_transaction_id: UUID | None

class PaymentUpdate(BaseModel):
    pass

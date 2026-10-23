from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
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


class PaymentWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: UUID
    external_payment_id: UUID
    amount_minor: int = Field(
        strict=True,
        gt=0,
        le=9_223_372_036_854_775_807,
    )
    currency: Literal["RUB"]
    status: Literal["succeeded", "failed"]

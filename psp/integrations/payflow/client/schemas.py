from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PayFlowWebhookPayload(BaseModel):
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

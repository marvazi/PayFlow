from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_payment_id: UUID
    amount_minor: int = Field(strict=True, gt=0, le=9_223_372_036_854_775_807)
    currency: Literal["RUB"]


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    external_payment_id: UUID
    currency: Literal["RUB"]
    status: Literal["pending", "succeeded", "failed"]
    amount_minor: int
    created_at: datetime
    updated_at: datetime


class TransactionComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["succeeded", "failed"]

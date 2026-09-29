from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

class PSPTransactionResponse(BaseModel):
    id: UUID
    external_payment_id: UUID
    amount_minor: int
    currency: Literal["RUB"]
    status: Literal["pending", "succeeded", "failed"]
    created_at: datetime
    updated_at: datetime
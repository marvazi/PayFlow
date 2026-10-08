from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BIGINT, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from psp.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, nullable=False)
    external_payment_id: Mapped[UUID] = mapped_column(
        nullable=False,
        unique=True,
    )
    amount_minor: Mapped[int] = mapped_column(BIGINT, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "currency = 'RUB'",
            name="ck_transactions_currency",
        ),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_transactions_status",
        ),
    )

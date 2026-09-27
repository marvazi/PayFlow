from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func, ForeignKey, BIGINT, CheckConstraint, Index, text
from uuid import uuid4, UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.db.base import Base




class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT")
    )
    amount_minor: Mapped[int] = mapped_column(BIGINT, nullable=False)
    status: Mapped[str] = mapped_column(String(20),default="pending", nullable=False)
    currency: Mapped[str] = mapped_column(String(3),default="RUB", nullable=False)
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

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")

    __table_args__ = (
        CheckConstraint(
            "amount_minor > 0",
            name="ck_payments_amount_positive"
        ),
        CheckConstraint(
            "currency = 'RUB'",
            name="ck_payments_currency",
        ),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_payments_status",
        ),
        Index(
            "payments_one_pending_per_invoice_idx",
            "invoice_id",
            postgresql_where=text("status = 'pending'"),
            unique=True,
        ),
    )

if TYPE_CHECKING:
    from app.models.invoice import Invoice
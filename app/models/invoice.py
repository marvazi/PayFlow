from datetime import datetime
from sqlalchemy import DateTime, String, func, ForeignKey, BIGINT, CheckConstraint
from uuid import uuid4, UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.db.base import Base
from app.models.customer import Customer
from app.models.organization import Organization


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BIGINT, nullable=False)
    currency: Mapped[str] = mapped_column(String(3),default="RUB", nullable=False)
    status: Mapped[str] = mapped_column(String(20),default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id",ondelete="RESTRICT")
    )
    organization: Mapped["Organization"] = relationship(back_populates="invoices")

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT")
    )
    customer: Mapped["Customer"] = relationship(back_populates="invoices")

    __table_args__ = (
        CheckConstraint(
            "amount_minor > 0",
            name="ck_invoices_amount_positive"
        ),
        CheckConstraint(
            "currency = 'RUB'",
            name="ck_invoices_currency_name",
        )
    )


from datetime import datetime
from sqlalchemy import DateTime, String, func, Index, ForeignKey
from app.db.base import Base
from uuid import uuid4, UUID
from sqlalchemy.orm import mapped_column, Mapped


class Customer(Base):
    __tablename__ = 'customers'

    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255),nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "customers_org_email_unique_idx",
            "organization_id",
            func.lower(func.btrim(email)),
            unique=True,
        ),
    )
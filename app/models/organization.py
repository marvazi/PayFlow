from datetime import datetime
from sqlalchemy import DateTime, String, func
from app.db.base import Base
from uuid import uuid4, UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.invoice import Invoice

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(default=uuid4,primary_key=True)
    name: Mapped[str] = mapped_column(String(255),nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="organization",
        passive_deletes="all",
    )
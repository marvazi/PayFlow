from datetime import datetime
from sqlalchemy import DateTime, String, func, Index
from app.db.base import Base
from uuid import uuid4, UUID
from sqlalchemy.orm import mapped_column, Mapped

class User(Base):
    __tablename__ = 'users'

    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    __table_args__ = (
        Index(
            "users_email_unique_idx",
            func.lower(func.btrim(email)),
            unique=True,
        ),
    )
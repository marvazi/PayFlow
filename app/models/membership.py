from datetime import datetime
from sqlalchemy import DateTime,func, ForeignKey, Enum, UniqueConstraint
from app.db.base import Base
from uuid import uuid4, UUID
from sqlalchemy.orm import mapped_column, Mapped

class Membership(Base):
    __tablename__ = 'memberships'

    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Enum("owner", "manager", "viewer", name="membership_role"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "organization_id",
            name="memberships_user_org_unique",
        ),
    )
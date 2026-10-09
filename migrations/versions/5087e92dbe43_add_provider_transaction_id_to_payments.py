"""add provider transaction id to payments

Revision ID: 5087e92dbe43
Revises: 5709c4214853
Create Date: 2026-10-10 01:45:24.016851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5087e92dbe43'
down_revision: Union[str, Sequence[str], None] = '5709c4214853'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("provider_transaction_id", sa.Uuid(), nullable=True),
    )
    op.create_unique_constraint(
        "payments_provider_transaction_id_key",
        "payments",
        ["provider_transaction_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "payments_provider_transaction_id_key",
        "payments",
        type_="unique",
    )
    op.drop_column("payments", "provider_transaction_id")

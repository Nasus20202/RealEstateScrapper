"""listing attributes json

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "listings",
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.alter_column("listings", "attributes", server_default=None)


def downgrade() -> None:
    op.drop_column("listings", "attributes")

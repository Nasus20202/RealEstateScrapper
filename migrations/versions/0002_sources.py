"""sources

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_sources_source_id", "sources", ["source_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_sources_source_id", table_name="sources")
    op.drop_table("sources")

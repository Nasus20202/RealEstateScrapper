"""llm_analysis

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_analysis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("features", postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("listing_id", "content_hash", name="uq_analysis_listing_hash"),
    )
    op.create_index("ix_llm_analysis_listing_id", "llm_analysis", ["listing_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_analysis_listing_id", table_name="llm_analysis")
    op.drop_table("llm_analysis")

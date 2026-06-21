"""dedup groups/members

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dedup_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "dedup_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["dedup_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("listing_id", name="uq_dedup_member_listing"),
    )
    op.create_index("ix_dedup_members_group_id", "dedup_members", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_dedup_members_group_id", table_name="dedup_members")
    op.drop_table("dedup_members")
    op.drop_table("dedup_groups")

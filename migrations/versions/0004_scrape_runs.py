"""scrape_runs

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

scraperunstatus = postgresql.ENUM(
    "success", "blocked", "failed", name="scraperunstatus", create_type=False
)
_scraperunstatus_create = postgresql.ENUM(
    "success", "blocked", "failed", name="scraperunstatus"
)


def upgrade() -> None:
    bind = op.get_bind()
    _scraperunstatus_create.create(bind, checkfirst=True)
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", scraperunstatus, nullable=False),
        sa.Column("new_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gone_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("scrape_runs")
    _scraperunstatus_create.drop(op.get_bind(), checkfirst=True)

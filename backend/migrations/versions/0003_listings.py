"""listings + price_history

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-21
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from realestate.config import get_embedding_dim

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

market = postgresql.ENUM("primary", "secondary", name="markettype", create_type=False)
status = postgresql.ENUM("active", "gone", name="listingstatus", create_type=False)
_market_create = postgresql.ENUM("primary", "secondary", name="markettype")
_status_create = postgresql.ENUM("active", "gone", name="listingstatus")


def upgrade() -> None:
    bind = op.get_bind()
    _market_create.create(bind, checkfirst=True)
    _status_create.create(bind, checkfirst=True)
    dim = get_embedding_dim()
    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_per_m2", sa.Numeric(12, 2), nullable=True),
        sa.Column("area_m2", sa.Float(), nullable=True),
        sa.Column("rooms", sa.Integer(), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("total_floors", sa.Integer(), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("district", sa.String(128), nullable=True),
        sa.Column("street", sa.String(255), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("market", market, nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("images", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_hash", sa.String(64), nullable=False),
        sa.Column("status", status, nullable=False, server_default="active"),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("embedding", Vector(dim), nullable=True),
        sa.UniqueConstraint("source_id", "external_id", name="uq_source_external"),
    )
    op.create_index("ix_listings_source_id", "listings", ["source_id"])
    op.create_index("ix_listings_district", "listings", ["district"])
    op.create_index("ix_listings_raw_hash", "listings", ["raw_hash"])
    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "listing_id",
            sa.Integer(),
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("price_history")
    op.drop_index("ix_listings_raw_hash", table_name="listings")
    op.drop_index("ix_listings_district", table_name="listings")
    op.drop_index("ix_listings_source_id", table_name="listings")
    op.drop_table("listings")
    _status_create.drop(op.get_bind(), checkfirst=True)
    _market_create.drop(op.get_bind(), checkfirst=True)

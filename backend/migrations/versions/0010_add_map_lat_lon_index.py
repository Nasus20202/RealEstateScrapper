"""add map lat lon index

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-25
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_listings_lat_lon ON listings USING btree (lat, lon)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_listings_lat_lon")

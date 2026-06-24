"""add query indexes

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-25
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_price_history_listing_id_observed_at
            ON price_history USING btree (listing_id, observed_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_llm_analysis_listing_id_created_at
            ON llm_analysis USING btree (listing_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_listings_active_last_seen_id
            ON listings USING btree (last_seen DESC, id DESC)
            WHERE status = 'active'
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_listings_city ON listings USING btree (city)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_listings_city")
    op.execute("DROP INDEX IF EXISTS ix_listings_active_last_seen_id")
    op.execute("DROP INDEX IF EXISTS ix_llm_analysis_listing_id_created_at")
    op.execute("DROP INDEX IF EXISTS ix_price_history_listing_id_observed_at")

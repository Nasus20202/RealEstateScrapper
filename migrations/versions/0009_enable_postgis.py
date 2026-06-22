"""enable postgis when available

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-22
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'postgis') THEN
                CREATE EXTENSION IF NOT EXISTS postgis;
            ELSE
                RAISE NOTICE 'postgis extension is not available in this database image';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS postgis")

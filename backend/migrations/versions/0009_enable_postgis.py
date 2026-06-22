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
                ALTER TABLE listings
                    ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);
                CREATE INDEX IF NOT EXISTS ix_listings_geom
                    ON listings USING GIST (geom);
                CREATE OR REPLACE FUNCTION listings_sync_geom()
                RETURNS trigger AS $trigger$
                BEGIN
                    IF NEW.lon IS NULL OR NEW.lat IS NULL THEN
                        NEW.geom := NULL;
                    ELSE
                        NEW.geom := ST_SetSRID(ST_MakePoint(NEW.lon, NEW.lat), 4326);
                    END IF;
                    RETURN NEW;
                END;
                $trigger$ LANGUAGE plpgsql;
                DROP TRIGGER IF EXISTS trg_listings_sync_geom ON listings;
                CREATE TRIGGER trg_listings_sync_geom
                    BEFORE INSERT OR UPDATE OF lat, lon ON listings
                    FOR EACH ROW EXECUTE FUNCTION listings_sync_geom();
            ELSE
                RAISE NOTICE 'postgis extension is not available in this database image';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_listings_sync_geom ON listings")
    op.execute("DROP FUNCTION IF EXISTS listings_sync_geom()")
    op.execute("DROP INDEX IF EXISTS ix_listings_geom")
    op.execute("ALTER TABLE listings DROP COLUMN IF EXISTS geom")
    op.execute("DROP EXTENSION IF EXISTS postgis")

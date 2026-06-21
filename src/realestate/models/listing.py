from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from realestate.config import get_embedding_dim
from realestate.models.base import Base
from realestate.models.enums import ListingStatus, MarketType

# Wymiar embeddingu czytany bezpośrednio z env, aby import modelu NIE wymagał
# pełnej konfiguracji (Settings wymaga DATABASE_URL). Jedno źródło wartości: EMBEDDING_DIM.
_EMBEDDING_DIM = get_embedding_dim()


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_source_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)

    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_per_m2: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)

    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    market: Mapped[MarketType | None] = mapped_column(SAEnum(MarketType), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    raw_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[ListingStatus] = mapped_column(
        SAEnum(ListingStatus), default=ListingStatus.ACTIVE
    )
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBEDDING_DIM), nullable=True)

    price_history: Mapped[list[PriceHistory]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    listing: Mapped[Listing] = relationship(back_populates="price_history")

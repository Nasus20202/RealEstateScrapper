from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from realestate.models.base import Base


class LLMAnalysis(Base):
    __tablename__ = "llm_analysis"
    __table_args__ = (
        UniqueConstraint("listing_id", "content_hash", name="uq_analysis_listing_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)
    features: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from realestate.models.base import Base


class DedupGroup(Base):
    __tablename__ = "dedup_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    members: Mapped[list[DedupMember]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class DedupMember(Base):
    __tablename__ = "dedup_members"
    __table_args__ = (UniqueConstraint("listing_id", name="uq_dedup_member_listing"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("dedup_groups.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))

    group: Mapped[DedupGroup] = relationship(back_populates="members")

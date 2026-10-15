from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_source_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(30))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    engagement: Mapped[int] = mapped_column(Integer, default=0)

    relevant: Mapped[bool] = mapped_column(Boolean, default=True)
    classification_status: Mapped[str] = mapped_column(String(30), default="unclassified", index=True)

    platform: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    user_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    product_area: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    feature: Mapped[str | None] = mapped_column(String(120), nullable=True)
    feedback_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    sentiment: Mapped[str | None] = mapped_column(String(30), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(30), nullable=True)
    relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_change: Mapped[str | None] = mapped_column(Text, nullable=True)
    competitor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

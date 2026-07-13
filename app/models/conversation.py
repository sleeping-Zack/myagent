from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    visitor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitor_sessions.id", ondelete="CASCADE")
    )
    visitor_type: Mapped[str] = mapped_column(String(30), default="anonymous")
    title: Mapped[Optional[str]] = mapped_column(String(120))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    summarized_through_sequence: Mapped[int] = mapped_column(Integer, default=0)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    active_generation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    generation_started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    last_message_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    last_active_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

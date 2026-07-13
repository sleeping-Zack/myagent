from __future__ import annotations

import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "client_message_id", name="uq_message_client_request"
        ),
        UniqueConstraint(
            "conversation_id", "sequence_no", name="uq_message_sequence"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sequence_no: Mapped[Optional[int]] = mapped_column(Integer)
    client_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    regenerated_from_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    citation_ids: Mapped[list] = mapped_column(JSONB, default=list)
    citation_data: Mapped[list] = mapped_column(JSONB, default=list)
    model_name: Mapped[Optional[str]] = mapped_column(String(100))
    estimated_input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )

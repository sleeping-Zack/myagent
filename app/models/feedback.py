import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import SmallInteger, String, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class QuestionFeedback(Base):
    __tablename__ = "question_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), unique=True
    )
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger)
    reason: Mapped[Optional[str]] = mapped_column(String(100))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

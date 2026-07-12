import uuid
from typing import Optional
from datetime import datetime, date
from sqlalchemy import String, Text, Integer, Date, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    one_liner: Mapped[Optional[str]] = mapped_column(Text)
    project_type: Mapped[Optional[str]] = mapped_column(String(50))
    role_summary: Mapped[Optional[str]] = mapped_column(Text)
    tech_stack: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[Optional[str]] = mapped_column(String(30))
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    cover_image: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[Optional[str]] = mapped_column(String(100))
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(Text)
    related_links: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

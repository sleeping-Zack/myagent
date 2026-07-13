from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ConversationItem(BaseModel):
    id: UUID
    title: str
    message_count: int
    last_message_preview: Optional[str]
    updated_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationItem]


class MessageItem(BaseModel):
    id: UUID
    sequence_no: int
    role: Literal["user", "assistant"]
    content: str
    status: str
    citation_data: list[dict]
    latency_ms: Optional[int]
    created_at: datetime


class MessageList(BaseModel):
    items: list[MessageItem]
    has_more: bool

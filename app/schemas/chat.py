from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question: str = Field(..., max_length=500)
    conversation_id: Optional[UUID] = None
    stream: bool = True


class CitationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    section: Optional[str] = None
    project_slug: Optional[str] = None


class ChatMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: str


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: UUID
    rating: Literal[-1, 1]
    reason: Optional[Literal[
        "信息错误", "与问题无关", "引用不支持结论", "内容过长", "信息已过期"
    ]] = None
    comment: Optional[str] = Field(default=None, max_length=500)

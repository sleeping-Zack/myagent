from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question: str = Field(..., max_length=500)
    conversation_id: Optional[str] = None
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

    rating: int  # -1 or 1
    reason: Optional[str] = None
    comment: Optional[str] = None

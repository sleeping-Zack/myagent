from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    section: Optional[str] = None
    content_preview: str  # 前150字
    project_slug: Optional[str] = None
    tags: list[str] = []
    ranking_score: float

import uuid
from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ProjectCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    one_liner: Optional[str] = None
    project_type: Optional[str] = None
    role_summary: Optional[str] = None
    tech_stack: list = []
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    cover_image: Optional[str] = None
    sort_order: int = 0


class ProjectDetail(ProjectCard):
    pass

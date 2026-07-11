from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCard, ProjectDetail

router = APIRouter(prefix="/api/v1/projects")


@router.get("", response_model=list[ProjectCard])
async def list_projects(db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository()
    projects = await repo.get_all_public(db)
    return [ProjectCard.model_validate(p) for p in projects]


@router.get("/{slug}", response_model=ProjectDetail)
async def get_project(slug: str, db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository()
    project = await repo.get_by_slug(db, slug)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ProjectDetail.model_validate(project)

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.repositories.project_repository import ProjectRepository

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository()
    featured = await repo.get_all_public(db)
    featured = featured[:4]
    return templates.TemplateResponse("index.html", {"request": request, "projects": featured})


@router.get("/projects", response_class=HTMLResponse)
async def projects_list(request: Request, db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository()
    all_projects = await repo.get_all_public(db)
    return templates.TemplateResponse("projects.html", {"request": request, "projects": all_projects})


@router.get("/projects/{slug}", response_class=HTMLResponse)
async def project_detail(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository()
    project = await repo.get_by_slug(db, slug)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return templates.TemplateResponse("project_detail.html", {"request": request, "project": project})


@router.get("/agent", response_class=HTMLResponse)
async def agent_page(request: Request):
    return templates.TemplateResponse("agent.html", {"request": request})


@router.get("/resume", response_class=HTMLResponse)
async def resume_page(request: Request):
    return templates.TemplateResponse("resume.html", {"request": request})


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

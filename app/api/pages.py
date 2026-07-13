import json
from pathlib import Path
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.repositories.project_repository import ProjectRepository
from app.core.config import get_settings
from app.core.html_sanitizer import safe_url, sanitize_html

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters["safe_url"] = safe_url
templates.env.filters["sanitize_html"] = sanitize_html
EVALUATION_RESULT = Path("static/evaluation/latest.json")


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


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})


@router.get("/evaluation", response_class=HTMLResponse)
async def evaluation_page(request: Request):
    result = None
    if EVALUATION_RESULT.exists():
        result = json.loads(EVALUATION_RESULT.read_text(encoding="utf-8"))
    return templates.TemplateResponse(
        "evaluation.html",
        {"request": request, "result": result},
    )


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    site_url = get_settings().site_url.rstrip("/")
    return f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n"


@router.get("/sitemap.xml")
async def sitemap(db: AsyncSession = Depends(get_db)):
    site_url = get_settings().site_url.rstrip("/")
    paths = ["", "/projects", "/agent", "/resume", "/about", "/evaluation", "/privacy"]
    projects = await ProjectRepository().get_all_public(db)
    paths.extend(f"/projects/{project.slug}" for project in projects)
    urls = "".join(f"<url><loc>{site_url}{path}</loc></url>" for path in paths)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return Response(xml, media_type="application/xml")

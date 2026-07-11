from contextlib import asynccontextmanager
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import structlog

from app.core.config import get_settings
from app.core.database import engine, Base
from app.core.logging import setup_logging
from app.api import pages, chat, projects, feedback, health

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("startup", env=settings.app_env, model=settings.deepseek_model)
    yield
    await engine.dispose()
    logger.info("shutdown")


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 路由
app.include_router(health.router)
app.include_router(pages.router)
app.include_router(chat.router)
app.include_router(projects.router)
app.include_router(feedback.router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error("unhandled_exception", path=str(request.url), error=str(exc), traceback=tb)
    return PlainTextResponse(f"Internal Server Error\n{tb}", status_code=500)

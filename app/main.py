from contextlib import asynccontextmanager
import secrets
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import structlog

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.core.logging import setup_logging
from app.api import pages, chat, projects, feedback, health
from app.repositories.conversation_repository import ConversationRepository

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("startup", env=settings.app_env, model=settings.deepseek_model)
    if settings.conversation_retention_days is not None:
        try:
            async with AsyncSessionLocal() as session:
                deleted = await ConversationRepository().delete_expired(
                    session, settings.conversation_retention_days
                )
            logger.info("conversation_retention_cleanup", deleted=deleted)
        except Exception as exc:
            logger.warning("conversation_retention_cleanup_failed", error=str(exc))
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


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    csp_nonce = secrets.token_urlsafe(16)
    request.state.csp_nonce = csp_nonce
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{csp_nonce}'; "
        "style-src 'self'; "
        "img-src 'self' data:; font-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
        "form-action 'self'"
    )
    if settings.app_env == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response

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
    request_id = str(uuid.uuid4())
    logger.exception(
        "unhandled_exception",
        request_id=request_id,
        path=str(request.url),
        error=str(exc),
    )
    return JSONResponse(
        {"error": "服务暂时不可用", "request_id": request_id},
        status_code=500,
    )

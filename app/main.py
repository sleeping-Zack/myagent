from contextlib import asynccontextmanager
import asyncio
import secrets
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class ProxyHeadersMiddleware:
    """Trust X-Forwarded-Proto header from reverse proxy."""

    def __init__(self, app: ASGIApp, trusted_hosts: list[str] | None = None) -> None:
        self.app = app
        self.trusted_hosts = trusted_hosts or ["*"]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            if b"x-forwarded-proto" in headers:
                scope["scheme"] = headers[b"x-forwarded-proto"].decode("latin1")
        return await self.app(scope, receive, send)
import structlog

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.core.logging import setup_logging
from app.api import admin, pages, chat, projects, feedback, health, conversations
from app.repositories.conversation_repository import ConversationRepository

logger = structlog.get_logger()


async def cleanup_expired_conversations(retention_days: int) -> None:
    async with AsyncSessionLocal() as session:
        deleted = await ConversationRepository().delete_expired(
            session, retention_days
        )
    logger.info("conversation_retention_cleanup", deleted=deleted)


async def retention_worker(stop: asyncio.Event, retention_days: int) -> None:
    while True:
        try:
            await asyncio.wait_for(stop.wait(), timeout=24 * 60 * 60)
            return
        except asyncio.TimeoutError:
            try:
                await cleanup_expired_conversations(retention_days)
            except Exception as exc:
                logger.warning("conversation_retention_cleanup_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    settings.validate_production()
    logger.info("startup", env=settings.app_env, model=settings.deepseek_model)
    retention_stop = asyncio.Event()
    retention_task = None
    if settings.conversation_retention_days is not None:
        try:
            await cleanup_expired_conversations(settings.conversation_retention_days)
        except Exception as exc:
            logger.warning("conversation_retention_cleanup_failed", error=str(exc))
        retention_task = asyncio.create_task(
            retention_worker(retention_stop, settings.conversation_retention_days)
        )
    try:
        yield
    finally:
        retention_stop.set()
        if retention_task is not None:
            await retention_task
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

allowed_hosts = settings.effective_allowed_hosts()
if allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Trust X-Forwarded-Proto header from reverse proxy
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])


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
        f"style-src 'self' 'nonce-{csp_nonce}'; "
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
app.include_router(conversations.router)
app.include_router(admin.router)

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

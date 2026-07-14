from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.rate_limit import admin_auth_rate_limiter
from app.core.security import get_client_ip, hash_ip
from app.models.feedback import QuestionFeedback
from app.repositories.conversation_repository import ConversationRepository


router = APIRouter(prefix="/admin", include_in_schema=False)
templates = Jinja2Templates(directory="templates")
security = HTTPBasic(auto_error=False)


def display_question(value: str | None) -> str:
    question = (value or "").strip()
    if not question:
        return "无有效提问"
    if question.count("?") >= 5 and question.count("?") / len(question) >= 0.3:
        return "历史问题（原始记录编码异常）"
    return question


def validate_admin_credentials(
    credentials: HTTPBasicCredentials | None,
    settings: Settings,
) -> bool:
    if not settings.admin_password:
        raise HTTPException(status_code=503, detail="管理端尚未配置")
    return credentials is not None and secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.admin_username.encode("utf-8"),
    ) and secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.admin_password.encode("utf-8"),
    )


async def require_admin(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> None:
    client_ip = get_client_ip(request)
    allowed_ips = settings.csv_values("admin_allowed_ips")
    if allowed_ips and client_ip not in allowed_ips:
        raise HTTPException(status_code=403, detail="管理端不允许从当前地址访问")

    valid = validate_admin_credentials(credentials, settings)
    if not valid:
        if not await admin_auth_rate_limiter.allow(
            "admin-auth:" + hash_ip(client_ip),
            minute_limit=settings.admin_failed_login_ip_minute_limit,
            daily_limit=settings.admin_failed_login_ip_minute_limit,
            count_daily=False,
        ):
            raise HTTPException(
                status_code=429,
                detail="管理员认证失败次数过多",
                headers={"Retry-After": "60"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员认证失败",
            headers={"WWW-Authenticate": 'Basic realm="Personal Agent Admin"'},
        )


@router.get("", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_dashboard(
    request: Request,
    q: str = "",
    db: AsyncSession = Depends(get_db),
):
    search = q.strip()[:100]
    repository = ConversationRepository()
    rows = await repository.list_for_admin(db, search=search)
    conversations = [
        {
            "conversation": conversation,
            "question": display_question(first_question or conversation.title),
            "preview": latest_preview,
        }
        for conversation, first_question, latest_preview in rows
    ]
    stats = await repository.admin_stats(db)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "conversations": conversations,
            "stats": stats,
            "search": search,
        },
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )


@router.get(
    "/api/conversations/{conversation_id}",
    dependencies=[Depends(require_admin)],
)
async def admin_conversation_detail(
    conversation_id: uuid.UUID,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    repository = ConversationRepository()
    conversation = await repository.get_for_admin(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = await repository.get_messages(db, conversation.id, limit=100)
    message_ids = [message.id for message in messages]
    feedback_by_message: dict[uuid.UUID, QuestionFeedback] = {}
    if message_ids:
        result = await db.execute(
            select(QuestionFeedback).where(
                QuestionFeedback.message_id.in_(message_ids)
            )
        )
        feedback_by_message = {
            item.message_id: item
            for item in result.scalars().all()
            if item.message_id is not None
        }

    first_user_question = next(
        (message.content for message in messages if message.role == "user"),
        conversation.title,
    )
    return {
        "id": str(conversation.id),
        "visitor_id": str(conversation.visitor_id) if conversation.visitor_id else None,
        "title": display_question(first_user_question),
        "status": conversation.status,
        "created_at": conversation.created_at.isoformat(),
        "last_active_at": conversation.last_active_at.isoformat(),
        "messages": [
            {
                "id": str(message.id),
                "role": message.role,
                "content": (
                    display_question(message.content)
                    if message.role == "user" else message.content
                ),
                "status": message.status,
                "model_name": message.model_name,
                "latency_ms": message.latency_ms,
                "created_at": message.created_at.isoformat(),
                "citations": message.citation_data or [],
                "feedback": (
                    {
                        "rating": feedback_by_message[message.id].rating,
                        "reason": feedback_by_message[message.id].reason,
                        "comment": feedback_by_message[message.id].comment,
                    }
                    if message.id in feedback_by_message else None
                ),
            }
            for message in messages
            if message.role in {"user", "assistant"}
        ],
    }

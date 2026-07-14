from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chat import FeedbackRequest
from app.core.config import get_settings
from app.core.rate_limit import feedback_rate_limiter
from app.core.security import get_client_ip, hash_ip
from app.services.visitor_session_service import visitor_session_service
import uuid

router = APIRouter(prefix="/api/v1/messages")


@router.post("/{message_id}/feedback")
async def submit_feedback(
    message_id: str,
    body: FeedbackRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    client_ip = get_client_ip(request)
    if not feedback_rate_limiter.allow(
        hash_ip(client_ip),
        minute_limit=settings.feedback_ip_minute_limit,
        daily_limit=settings.feedback_daily_limit,
    ):
        raise HTTPException(
            status_code=429,
            detail="反馈提交过于频繁，请稍后再试",
            headers={"Retry-After": "60"},
        )
    try:
        mid = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 message_id")
    repo = ConversationRepository()
    visitor = await visitor_session_service.get_existing(request, db)
    if visitor is None:
        raise HTTPException(status_code=404, detail="消息不属于当前会话")
    if not await repo.message_belongs_to_conversation(
        db, mid, body.conversation_id, visitor.id
    ):
        raise HTTPException(status_code=404, detail="消息不属于当前会话")

    await repo.save_feedback(db, {
        "message_id": mid,
        "rating": body.rating,
        "reason": body.reason,
        "comment": body.comment,
    })
    return {"ok": True}

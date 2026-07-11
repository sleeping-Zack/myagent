from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chat import FeedbackRequest
import uuid

router = APIRouter(prefix="/api/v1/messages")


@router.post("/{message_id}/feedback")
async def submit_feedback(
    message_id: str,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        mid = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 message_id")
    repo = ConversationRepository(db)
    await repo.save_feedback(mid, body.rating, body.reason, body.comment)
    return {"ok": True}

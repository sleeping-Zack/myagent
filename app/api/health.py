from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.deepseek_service import DeepSeekService, get_deepseek_service

router = APIRouter()


@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(
    db: AsyncSession = Depends(get_db),
    embedding: EmbeddingService = Depends(get_embedding_service),
    model: DeepSeekService = Depends(get_deepseek_service),
):
    ready_status = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        ready_status = False

    ready_status = (
        ready_status
        and embedding.is_configured()
        and model.is_configured()
    )

    payload = {"status": "ok" if ready_status else "not_ready"}
    if ready_status:
        return payload
    return JSONResponse(payload, status_code=503)


@router.get("/health")
async def health_alias():
    return {"status": "ok"}

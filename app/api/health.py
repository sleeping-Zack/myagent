from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.services.embedding_service import EmbeddingService

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    # 检查数据库
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    embedding_status = "ok"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "embedding": embedding_status,
    }

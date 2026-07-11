import json
import traceback
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.config import get_settings
from app.schemas.chat import ChatRequest
from app.services.rag_service import RagService
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import RetrievalService
from app.services.deepseek_service import DeepSeekService
from app.services.citation_service import CitationService
from app.services.conversation_service import ConversationService
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.conversation_repository import ConversationRepository

router = APIRouter(prefix="/api/v1")


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()

    # 输入校验
    if not body.question or not body.question.strip():
        async def err():
            yield 'data: {"error": "问题不能为空"}\n\n'
        return StreamingResponse(err(), media_type="text/event-stream")

    if len(body.question) > settings.max_question_length:
        async def err():
            yield f'data: {{"error": "问题过长，最多 {settings.max_question_length} 字"}}\n\n'
        return StreamingResponse(err(), media_type="text/event-stream")

    # 组装服务
    embedding_svc = EmbeddingService()
    deepseek_svc = DeepSeekService()
    chunk_repo = ChunkRepository()
    retrieval_svc = RetrievalService(chunk_repo, embedding_svc)
    citation_svc = CitationService()
    conv_repo = ConversationRepository()
    conversation_svc = ConversationService(conv_repo, db)

    rag = RagService(
        retrieval_svc=retrieval_svc,
        deepseek_svc=deepseek_svc,
        citation_svc=citation_svc,
        conversation_svc=conversation_svc,
    )

    conversation_id = body.conversation_id

    async def event_stream():
        async for item in rag.answer(
            question=body.question,
            conversation_id=conversation_id,
            session=db,
        ):
            event_type = item["event"]
            data = item["data"]
            yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

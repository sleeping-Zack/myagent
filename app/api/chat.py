import json
import asyncio
import hashlib
import uuid
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.config import get_settings
from app.core.rate_limit import chat_rate_limiter
from app.core.security import is_safe_question
from app.schemas.chat import ChatRequest
from app.services.rag_service import RagService
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.retrieval_service import RetrievalService
from app.services.deepseek_service import DeepSeekService, get_deepseek_service
from app.services.citation_service import CitationService
from app.services.conversation_service import ConversationService
from app.services.hr_faq_service import get_pinned_hr_answer
from app.services.rag_service import follow_up_suggestions
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.conversation_repository import ConversationRepository

router = APIRouter(prefix="/api/v1")


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
    deepseek_svc: DeepSeekService = Depends(get_deepseek_service),
):
    settings = get_settings()

    client_ip = request.headers.get("x-real-ip") or (
        request.client.host if request.client else "unknown"
    )
    client_key = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()
    if not chat_rate_limiter.allow(
        client_key,
        minute_limit=settings.chat_ip_minute_limit,
        daily_limit=settings.chat_daily_limit,
    ):
        return JSONResponse(
            {"error": "请求过于频繁，请稍后再试"},
            status_code=429,
            headers={"Retry-After": "60"},
        )

    # 输入校验
    if not body.question or not body.question.strip():
        async def err():
            yield 'event: error\ndata: {"message": "问题不能为空"}\n\n'
        return StreamingResponse(err(), media_type="text/event-stream")

    if len(body.question) > settings.max_question_length:
        async def err():
            yield f'event: error\ndata: {{"message": "问题过长，最多 {settings.max_question_length} 字"}}\n\n'
        return StreamingResponse(err(), media_type="text/event-stream")

    if not is_safe_question(body.question):
        async def unsafe():
            yield 'event: token\ndata: {"content": "该请求涉及系统指令、私密信息或批量导出，无法处理。"}\n\n'
            yield 'event: done\ndata: {"message_id": "", "suggestions": []}\n\n'
        return StreamingResponse(unsafe(), media_type="text/event-stream")

    conversation_id = str(body.conversation_id) if body.conversation_id else str(uuid.uuid4())
    conv_repo = ConversationRepository()
    conversation_svc = ConversationService(conv_repo, db)

    # 组装服务
    pinned_answer = get_pinned_hr_answer(body.question)
    if pinned_answer:
        async def pinned_stream():
            yield f'event: meta\ndata: {{"conversation_id": "{conversation_id}"}}\n\n'
            source = {
                "id": "hr-faq",
                "title": "06_hr_interview_qa.md",
                "section": body.question.strip(),
                "content_preview": pinned_answer[:150],
                "project_slug": None,
                "tags": ["hr", "faq"],
            }
            yield f"event: source\ndata: {json.dumps(source, ensure_ascii=False)}\n\n"
            for start in range(0, len(pinned_answer), 18):
                token = pinned_answer[start:start + 18]
                yield f"event: token\ndata: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)
            message_id = await conversation_svc.save_exchange(
                conversation_id=conversation_id,
                question=body.question,
                answer=pinned_answer,
                citation_ids=[],
                model_name="pinned-hr-faq",
                estimated_input_tokens=0,
                estimated_output_tokens=0,
                latency_ms=0,
            )
            done = {
                "message_id": message_id,
                "suggestions": follow_up_suggestions(body.question),
            }
            yield f"event: done\ndata: {json.dumps(done, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            pinned_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    chunk_repo = ChunkRepository()
    retrieval_svc = RetrievalService(chunk_repo, embedding_svc)
    citation_svc = CitationService()

    rag = RagService(
        retrieval_svc=retrieval_svc,
        deepseek_svc=deepseek_svc,
        citation_svc=citation_svc,
        conversation_svc=conversation_svc,
    )

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

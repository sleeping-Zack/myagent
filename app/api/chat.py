import asyncio
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import chat_rate_limiter, visitor_create_rate_limiter
from app.core.security import get_client_ip, hash_ip, is_safe_question
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chat import ChatRequest
from app.services.citation_service import CitationService
from app.services.conversation_service import ConversationService
from app.services.deepseek_service import DeepSeekService, get_deepseek_service
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.hr_faq_service import get_greeting_answer, get_pinned_hr_answer
from app.services.rag_service import RagService, follow_up_suggestions
from app.services.retrieval_service import RetrievalService
from app.services.visitor_session_service import visitor_session_service


router = APIRouter(prefix="/api/v1")
logger = structlog.get_logger()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    embedding_svc: EmbeddingService = Depends(get_embedding_service),
    deepseek_svc: DeepSeekService = Depends(get_deepseek_service),
):
    settings = get_settings()
    question = body.question.strip()

    if not question:
        async def empty_error():
            yield _sse("error", {"message": "问题不能为空"})
        return StreamingResponse(empty_error(), media_type="text/event-stream")

    if not is_safe_question(question):
        async def unsafe_error():
            yield _sse("token", {"content": "该请求涉及系统指令、私密信息或批量导出，无法处理。"})
            yield _sse("done", {"message_id": "", "suggestions": []})
        return StreamingResponse(unsafe_error(), media_type="text/event-stream")

    client_ip = get_client_ip(request)
    visitor = await visitor_session_service.get_existing(request, db)
    if visitor is None:
        if not visitor_create_rate_limiter.allow(
            "new-visitor:" + hash_ip(client_ip),
            minute_limit=settings.visitor_create_ip_minute_limit,
            daily_limit=settings.visitor_create_daily_limit,
        ):
            return JSONResponse(
                {"error": "新建匿名会话过于频繁，请稍后再试"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        visitor = await visitor_session_service.create(db)
    ip_key = "ip:" + hashlib.sha256(client_ip.encode("utf-8")).hexdigest()
    visitor_key = f"visitor:{visitor.id}"
    if not chat_rate_limiter.allow(
        ip_key,
        minute_limit=settings.chat_ip_minute_limit,
        daily_limit=settings.chat_daily_limit,
        count_daily=False,
    ) or not chat_rate_limiter.allow(
        visitor_key,
        minute_limit=settings.chat_visitor_minute_limit,
        daily_limit=settings.chat_daily_limit,
    ):
        response = JSONResponse(
            {"error": "请求过于频繁，请稍后再试"},
            status_code=429,
            headers={"Retry-After": "60"},
        )
        visitor_session_service.set_cookie(response, visitor)
        return response

    repository = ConversationRepository()
    if body.conversation_id:
        conversation = await repository.get_owned(
            db, body.conversation_id, visitor.id
        )
        if conversation is None:
            response = JSONResponse({"error": "会话不存在"}, status_code=404)
            visitor_session_service.set_cookie(response, visitor)
            return response
    else:
        conversation = await repository.create_conversation(db, visitor.id)

    if (conversation.message_count or 0) >= 40:
        response = JSONResponse(
            {"error": "当前会话已达到 20 轮上限，请新建对话"}, status_code=429
        )
        visitor_session_service.set_cookie(response, visitor)
        return response

    generation_id = uuid.uuid4()
    if not await repository.try_start_generation(
        db, conversation.id, visitor.id, generation_id
    ):
        response = JSONResponse(
            {"error": "当前会话正在生成回答"}, status_code=409
        )
        visitor_session_service.set_cookie(response, visitor)
        return response

    client_message_id = body.client_message_id or uuid.uuid4()
    if await repository.find_client_message(
        db, conversation.id, client_message_id
    ):
        await repository.finish_generation(db, conversation.id, generation_id)
        response = JSONResponse({"error": "该消息已提交"}, status_code=409)
        visitor_session_service.set_cookie(response, visitor)
        return response

    conversation_service = ConversationService(repository, db)
    memory = await conversation_service.build_memory(conversation)
    await repository.create_message(
        db,
        conversation,
        role="user",
        content=question,
        status="completed",
        client_message_id=client_message_id,
    )
    assistant_message = await repository.create_message(
        db,
        conversation,
        role="assistant",
        content="",
        status="streaming",
        message_id=generation_id,
    )

    rag = RagService(
        retrieval_svc=RetrievalService(
            ChunkRepository(), embedding_svc
        ),
        deepseek_svc=deepseek_svc,
        citation_svc=CitationService(),
    )

    async def event_stream():
        answer_parts: list[str] = []
        completed = False
        try:
            yield _sse("meta", {"conversation_id": str(conversation.id)})
            greeting_answer = get_greeting_answer(question)
            pinned_answer = get_pinned_hr_answer(question)
            if greeting_answer:
                for start in range(0, len(greeting_answer), 18):
                    token = greeting_answer[start:start + 18]
                    answer_parts.append(token)
                    yield _sse("token", {"content": token})
                    await asyncio.sleep(0.02)
                metadata = {
                    "citation_ids": [],
                    "citations": [],
                    "model_name": "static-greeting",
                    "estimated_input_tokens": 0,
                    "estimated_output_tokens": 0,
                    "latency_ms": 0,
                    "suggestions": follow_up_suggestions(question),
                }
            elif pinned_answer:
                source = {
                    "id": "hr-faq",
                    "title": "06_hr_interview_qa.md",
                    "section": question,
                    "content_preview": pinned_answer[:150],
                    "project_slug": None,
                    "tags": ["hr", "faq"],
                }
                yield _sse("source", source)
                for start in range(0, len(pinned_answer), 18):
                    token = pinned_answer[start:start + 18]
                    answer_parts.append(token)
                    yield _sse("token", {"content": token})
                    await asyncio.sleep(0.02)
                metadata = {
                    "citation_ids": [],
                    "citations": [source],
                    "model_name": "pinned-hr-faq",
                    "estimated_input_tokens": 0,
                    "estimated_output_tokens": 0,
                    "latency_ms": 0,
                    "suggestions": follow_up_suggestions(question),
                }
            else:
                metadata = None
                async for item in rag.answer(
                    question=question,
                    conversation_id=str(conversation.id),
                    session=db,
                    context_messages=memory.recent_messages,
                    conversation_summary=memory.summary,
                ):
                    event_type = item["event"]
                    data = item["data"]
                    if event_type == "meta":
                        continue
                    if event_type == "token":
                        answer_parts.append(data.get("content", ""))
                    if event_type == "done":
                        metadata = data
                        continue
                    yield _sse(event_type, data)

            full_answer = "".join(answer_parts)
            metadata = metadata or {}
            await repository.complete_assistant_message(
                db,
                assistant_message.id,
                content=full_answer,
                status="completed",
                citation_ids=metadata.get("citation_ids", []),
                citation_data=metadata.get("citations", []),
                model_name=metadata.get("model_name"),
                estimated_input_tokens=metadata.get("estimated_input_tokens"),
                estimated_output_tokens=metadata.get("estimated_output_tokens"),
                latency_ms=metadata.get("latency_ms"),
            )
            completed = True
            yield _sse("done", {
                "message_id": str(assistant_message.id),
                "suggestions": metadata.get("suggestions", []),
            })
        except asyncio.CancelledError:
            await repository.complete_assistant_message(
                db,
                assistant_message.id,
                content="".join(answer_parts) or "已停止生成。",
                status="stopped",
            )
            raise
        except Exception as exc:
            logger.exception(
                "chat_generation_failed",
                conversation_id=str(conversation.id),
                generation_id=str(generation_id),
                error=str(exc),
            )
            await repository.complete_assistant_message(
                db,
                assistant_message.id,
                content="".join(answer_parts) or "生成失败，请重试。",
                status="failed",
            )
            yield _sse("error", {"message": "回答生成失败，请稍后重试。"})
        finally:
            if not completed and not answer_parts:
                # The failure/cancellation handlers persist a visible state.
                pass
            await repository.finish_generation(
                db, conversation.id, generation_id
            )

    streaming_response = StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    visitor_session_service.set_cookie(streaming_response, visitor)
    return streaming_response

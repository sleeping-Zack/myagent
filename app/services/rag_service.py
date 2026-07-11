import asyncio
import re
import time
import uuid
from pathlib import Path
from typing import AsyncIterator, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.services.retrieval_service import RetrievalService
from app.services.deepseek_service import DeepSeekService
from app.services.citation_service import CitationService
from app.services.conversation_service import ConversationService
from app.schemas.citation import CitationOut
from app.core.config import settings

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_SENSITIVE_PATTERNS = [
    r"sk-[A-Za-z0-9]{20,}",                          # API key 格式
    r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d+\.\d+\b",  # 私有 IP
    r"-----BEGIN [A-Z ]+-----",                        # PEM 密钥
]
_SENSITIVE_RE = re.compile("|".join(_SENSITIVE_PATTERNS))


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


class RagService:
    def __init__(
        self,
        retrieval_svc: RetrievalService,
        deepseek_svc: DeepSeekService,
        citation_svc: CitationService,
        conversation_svc: ConversationService,
    ) -> None:
        self._retrieval = retrieval_svc
        self._deepseek = deepseek_svc
        self._citation = citation_svc
        self._conv = conversation_svc

    async def answer(
        self,
        question: str,
        conversation_id: Optional[str],
        session: "AsyncSession",
        stream: bool = True,
    ) -> AsyncIterator[dict]:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        # 1. 敏感词检测
        if _SENSITIVE_RE.search(question):
            yield {"event": "token", "data": {"content": "问题包含敏感内容，无法处理。"}}
            yield {"event": "done", "data": {"message_id": ""}}
            return

        yield {"event": "meta", "data": {"conversation_id": conversation_id}}

        start_ms = int(time.time() * 1000)

        # 2. 检索
        chunks = await self._retrieval.retrieve(
            question,
            session=session,
            top_k=settings.retrieval_top_k,
            min_score=settings.min_relevance_score,
        )

        # 3. 证据充分性判断
        if not self._citation.has_sufficient_evidence(
            chunks, question, min_score=settings.min_relevance_score
        ):
            insufficient_tmpl = _load_prompt("insufficient_evidence.txt")
            # 整理现有最高分 chunk 摘要作为 available_info
            available_info = "暂无相关信息。" if not chunks else chunks[0]["content"][:80]
            fallback_text = insufficient_tmpl.replace("{available_info}", available_info)
            message_id = await self._conv.save_exchange(
                conversation_id=conversation_id,
                question=question,
                answer=fallback_text,
                citation_ids=[],
                model_name=settings.deepseek_model,
                input_tokens=await self._deepseek.count_tokens(question),
                output_tokens=await self._deepseek.count_tokens(fallback_text),
                latency_ms=int(time.time() * 1000) - start_ms,
            )
            yield {"event": "token", "data": {"content": fallback_text}}
            yield {"event": "done", "data": {"message_id": message_id}}
            return

        # 4. 格式化引用
        top_chunks = chunks[: settings.max_context_chunks]
        citations: list[CitationOut] = self._citation.format_citations(top_chunks)

        # 5. 先 yield source 事件（前端立即显示引用卡片）
        for c in citations:
            yield {"event": "source", "data": c.model_dump()}

        # 6. 构建 messages
        system_prompt = _load_prompt("system_prompt.txt")
        answer_tmpl = _load_prompt("answer_prompt.txt")

        context_messages = await self._conv.get_context(conversation_id, last_n=6)
        conversation_context = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in context_messages
        ) or "（无历史对话）"

        retrieved_chunks_text = "\n\n".join(
            f"[{i+1}] {c['title']}"
            + (f"（{c['section']}）" if c.get("section") else "")
            + f"\n{c['content']}"
            for i, c in enumerate(top_chunks)
        )

        user_message = answer_tmpl.format(
            question=question,
            conversation_context=conversation_context,
            retrieved_chunks=retrieved_chunks_text,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *context_messages,
            {"role": "user", "content": user_message},
        ]

        # 7. 流式输出
        answer_parts: list[str] = []
        async for token in self._deepseek.stream_chat(messages):
            answer_parts.append(token)
            yield {"event": "token", "data": {"content": token}}

        full_answer = "".join(answer_parts)
        latency_ms = int(time.time() * 1000) - start_ms

        # 8. 保存问答日志
        citation_ids = [c.id for c in citations]
        input_tokens = await self._deepseek.count_tokens(user_message + system_prompt)
        output_tokens = await self._deepseek.count_tokens(full_answer)

        message_id = await self._conv.save_exchange(
            conversation_id=conversation_id,
            question=question,
            answer=full_answer,
            citation_ids=citation_ids,
            model_name=settings.deepseek_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

        yield {"event": "done", "data": {"message_id": message_id}}

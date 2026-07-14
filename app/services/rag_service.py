from __future__ import annotations

import re
import time
from pathlib import Path
from typing import AsyncIterator, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.services.retrieval_service import RetrievalService
from app.services.deepseek_service import DeepSeekService
from app.services.citation_service import CitationService
from app.schemas.citation import CitationOut
from app.core.config import settings

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_SENSITIVE_PATTERNS = [
    r"sk-[A-Za-z0-9]{20,}",                          # API key 格式
    r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d+\.\d+\b",  # 私有 IP
    r"-----BEGIN [A-Z ]+-----",                        # PEM 密钥
    r"(?i:\b(?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+-]{12,})",
]
_SENSITIVE_RE = re.compile("|".join(_SENSITIVE_PATTERNS))


def redact_sensitive_text(value: str) -> str:
    return _SENSITIVE_RE.sub("[REDACTED]", value)


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


def follow_up_suggestions(question: str) -> list[str]:
    q = question.lower()
    if "法奥" in q or "farino" in q or "aiflowy" in q:
        return ["这个项目中朱旭具体负责哪些模块？", "Direct 和 Agentic 路由如何实现？"]
    if "智扫" in q or "扫地机器人" in q or "budget" in q:
        return ["混合检索的离线评测结果如何？", "BudgetManager 如何控制 Agent？"]
    if "实习" in q or "长冈" in q or "血压计" in q:
        return ["这段嵌入式经历对 Agent 开发有什么帮助？", "实习中解决过哪些稳定性问题？"]
    return ["朱旭最有代表性的项目是什么？", "他的能力边界和当前不足是什么？"]


class RagService:
    def __init__(
        self,
        retrieval_svc: RetrievalService,
        deepseek_svc: DeepSeekService,
        citation_svc: CitationService,
    ) -> None:
        self._retrieval = retrieval_svc
        self._deepseek = deepseek_svc
        self._citation = citation_svc

    async def answer(
        self,
        question: str,
        conversation_id: str,
        session: "AsyncSession",
        context_messages: list[dict[str, str]] | None = None,
        conversation_summary: str = "",
    ) -> AsyncIterator[dict]:
        # 1. 敏感词检测
        if _SENSITIVE_RE.search(question):
            yield {"event": "token", "data": {"content": "问题包含敏感内容，无法处理。"}}
            yield {"event": "done", "data": {"message_id": "", "suggestions": []}}
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
            yield {"event": "token", "data": {"content": fallback_text}}
            yield {"event": "done", "data": {
                "citation_ids": [],
                "citations": [],
                "model_name": settings.deepseek_model,
                "estimated_input_tokens": self._deepseek.estimate_tokens(question),
                "estimated_output_tokens": self._deepseek.estimate_tokens(fallback_text),
                "latency_ms": int(time.time() * 1000) - start_ms,
                "suggestions": follow_up_suggestions(question),
            }}
            return

        # 4. 格式化引用
        top_chunks = [
            {**chunk, "content": redact_sensitive_text(chunk["content"])}
            for chunk in chunks[: settings.max_context_chunks]
        ]
        citations: list[CitationOut] = self._citation.format_citations(top_chunks)

        # 5. 先 yield source 事件（前端立即显示引用卡片）
        for c in citations:
            yield {"event": "source", "data": c.model_dump()}

        # 6. 构建 messages
        system_prompt = _load_prompt("system_prompt.txt")
        answer_tmpl = _load_prompt("answer_prompt.txt")

        context_messages = context_messages or []
        conversation_context = (
            "请参考前序对话消息保持上下文一致。"
            if context_messages else "（无历史对话）"
        )

        retrieved_chunks_text = "<knowledge_data>\n" + "\n\n".join(
            f"[{i+1}] {c['title']}"
            + (f"（{c['section']}）" if c.get("section") else "")
            + f"\n{c['content']}"
            for i, c in enumerate(top_chunks)
        ) + "\n</knowledge_data>"

        user_message = answer_tmpl.format(
            question=question,
            conversation_context=conversation_context,
            retrieved_chunks=retrieved_chunks_text,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *([{
                "role": "system",
                "content": f"<conversation_memory>\n{conversation_summary}\n</conversation_memory>",
            }] if conversation_summary else []),
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

        # 8. 返回持久化所需元数据，由 API 层更新预先创建的消息记录。
        citation_ids = [c.id for c in citations]
        estimated_input_tokens = self._deepseek.estimate_tokens(user_message + system_prompt)
        estimated_output_tokens = self._deepseek.estimate_tokens(full_answer)

        yield {"event": "done", "data": {
            "citation_ids": citation_ids,
            "citations": [citation.model_dump() for citation in citations],
            "model_name": settings.deepseek_model,
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "latency_ms": latency_ms,
            "suggestions": follow_up_suggestions(question),
        }}

from pathlib import Path
import re
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document
from app.repositories.chunk_repository import ChunkRepository
from app.services.embedding_service import EmbeddingService

_PROJECT_ALIASES = {
    "面向智能硬件客服场景的可治理agent平台": (
        "面向智能硬件客服场景的可治理agent平台",
        "智能硬件客服",
        "可治理agent平台",
        "agentproject",
    ),
    "法奥机器人": ("法奥", "法奥机器人", "farino", "aiflowy"),
    "个人招聘知识agent": ("个人agent", "招聘知识agent", "myagent", "本站"),
    "情绪分析日记": ("情绪分析", "心情助手", "moodtracker", "mood tracker"),
}


def _normalize(text: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text.lower())


def _cjk_bigrams(text: str) -> set[str]:
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    return {chinese[i:i + 2] for i in range(max(0, len(chinese) - 1))}


class RetrievalService:
    def __init__(self, chunk_repo: ChunkRepository, embedding_svc: EmbeddingService) -> None:
        self._chunk_repo = chunk_repo
        self._embedding_svc = embedding_svc

    async def retrieve(
        self,
        question: str,
        session: AsyncSession,
        top_k: int = 10,
        min_score: float = 0.40,
    ) -> list[dict]:
        embedding = await self._embedding_svc.async_embed_query(question)

        raw_chunks = await self._chunk_repo.search_similar(
            session=session,
            embedding=embedding,
            top_k=top_k * 2,
            visibility="public",
            confidence_levels=["confirmed", "self_reported"],
        )

        source_names = {}
        document_ids = {
            chunk.document_id for chunk, _ in raw_chunks if chunk.document_id
        }
        if document_ids:
            result = await session.execute(
                select(Document.id, Document.source_id).where(Document.id.in_(document_ids))
            )
            source_names = {
                row.id: Path(row.source_id).name
                for row in result
            }

        results: list[dict] = []
        for chunk, cosine_distance in raw_chunks:
            vector_score = max(0.0, min(1.0, 1.0 - cosine_distance))
            final_score = self._score(vector_score, chunk, question)
            if final_score >= min_score:
                results.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id) if chunk.document_id else None,
                    "title": chunk.title,
                    "section": chunk.section,
                    "content": chunk.content,
                    "score": round(final_score, 4),
                    "tags": chunk.tags or [],
                    "project_id": str(chunk.project_id) if chunk.project_id else None,
                    "source_name": source_names.get(chunk.document_id),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        deduplicated: list[dict] = []
        document_counts: dict[str, int] = {}
        for result in results:
            document_id = result.pop("document_id")
            if document_id:
                count = document_counts.get(document_id, 0)
                if count >= 2:
                    continue
                document_counts[document_id] = count + 1
            deduplicated.append(result)
        return deduplicated[:top_k]

    def _score(self, vector_score: float, chunk: Any, question: str) -> float:
        q_lower = question.lower()
        title_lower = (chunk.title or "").lower()
        q_normalized = _normalize(question)
        title_normalized = _normalize(title_lower)

        alias_match = any(
            any(_normalize(alias) in q_normalized for alias in aliases)
            and _normalize(canonical) in title_normalized
            for canonical, aliases in _PROJECT_ALIASES.items()
        )
        ngram_overlap = _cjk_bigrams(question).intersection(_cjk_bigrams(title_lower))
        title_match = 1.0 if alias_match or len(ngram_overlap) >= 2 else 0.0

        tags: list[str] = chunk.tags or []
        tag_match = 0.0
        for tag in tags:
            normalized_tag = _normalize(tag)
            if normalized_tag and normalized_tag in q_normalized:
                tag_match = 1.0
                break

        # project_match: 有 project_id 且问题提到项目相关词
        project_keywords = ["项目", "project", "经历", "实习", "开发"]
        project_match = 1.0 if chunk.project_id and any(k in q_lower for k in project_keywords) else 0.0

        return min(
            1.0,
            vector_score
            + title_match * 0.10
            + tag_match * 0.10
            + project_match * 0.05,
        )

import asyncio
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.chunk_repository import ChunkRepository
from app.services.embedding_service import EmbeddingService

# 关键词 → tag 强制匹配权重
_TAG_KEYWORDS: list[str] = [
    "RAG", "Agent", "DeepSeek", "Python", "FastAPI",
    "Java", "Spring Boot", "OpenHarmony", "UNISOC",
    "嵌入式", "网络安全", "血压计", "法奥机器人",
]


class RetrievalService:
    def __init__(self, chunk_repo: ChunkRepository, embedding_svc: EmbeddingService) -> None:
        self._chunk_repo = chunk_repo
        self._embedding_svc = embedding_svc

    async def retrieve(
        self,
        question: str,
        session: AsyncSession,
        top_k: int = 10,
        min_score: float = 0.45,
    ) -> list[dict]:
        embedding = await asyncio.to_thread(self._embedding_svc.embed_query, question)

        raw_chunks = await self._chunk_repo.search_similar(
            session=session,
            embedding=embedding,
            top_k=top_k,
            visibility="public",
            confidence_levels=["confirmed", "self_reported"],
        )

        results: list[dict] = []
        for i, chunk in enumerate(raw_chunks):
            # pgvector cosine distance → similarity: 1 - distance
            # 由于 <=> 返回距离，rank 0 最近，用位置估算 vector_score
            vector_score = max(0.0, 1.0 - i / max(len(raw_chunks), 1) * 0.6)
            final_score = self._score(vector_score, chunk, question)
            if final_score >= min_score:
                results.append({
                    "chunk_id": str(chunk.id),
                    "title": chunk.title,
                    "section": chunk.section,
                    "content": chunk.content,
                    "score": round(final_score, 4),
                    "tags": chunk.tags or [],
                    "project_id": str(chunk.project_id) if chunk.project_id else None,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def _score(self, vector_score: float, chunk: Any, question: str) -> float:
        q_lower = question.lower()
        title_lower = (chunk.title or "").lower()

        title_match = 1.0 if any(w in title_lower for w in q_lower.split()) else 0.0

        tags: list[str] = chunk.tags or []
        tag_match = 0.0
        for kw in _TAG_KEYWORDS:
            if kw.lower() in q_lower and any(kw.lower() in t.lower() for t in tags):
                tag_match = 1.0
                break

        # project_match: 有 project_id 且问题提到项目相关词
        project_keywords = ["项目", "project", "经历", "实习", "开发"]
        project_match = 1.0 if chunk.project_id and any(k in q_lower for k in project_keywords) else 0.0

        return (
            vector_score * 0.75
            + title_match * 0.10
            + tag_match * 0.10
            + project_match * 0.05
        )

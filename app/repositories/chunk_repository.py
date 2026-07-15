import uuid
from typing import Optional
from sqlalchemy import Float, case, func, literal, or_, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector
from sqlalchemy import cast
from app.models.chunk import DocumentChunk
from app.core.config import settings


class ChunkRepository:
    async def search_similar(
        self,
        session: AsyncSession,
        embedding: list[float],
        top_k: int = 10,
        visibility: str = "public",
        confidence_levels: Optional[list[str]] = None,
        project_ids: Optional[list[uuid.UUID]] = None,
        section_terms: Optional[list[str]] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        query_vec = cast(embedding, Vector(settings.embedding_dimensions))
        cosine_distance = cast(
            DocumentChunk.embedding.op("<=>")(query_vec),
            Float,
        )
        stmt = select(
            DocumentChunk,
            cosine_distance.label("cosine_distance"),
        ).where(
            DocumentChunk.visibility == visibility,
            DocumentChunk.embedding.is_not(None),
        )
        if confidence_levels:
            stmt = stmt.where(DocumentChunk.confidence.in_(confidence_levels))
        if project_ids:
            stmt = stmt.where(DocumentChunk.project_id.in_(project_ids))
        if section_terms:
            stmt = stmt.where(or_(*[
                func.coalesce(DocumentChunk.section, "").ilike(f"%{term}%")
                for term in section_terms
            ]))
        stmt = stmt.order_by(cosine_distance).limit(top_k)
        result = await session.execute(stmt)
        return [(chunk, float(distance)) for chunk, distance in result.all()]

    async def search_lexical(
        self,
        session: AsyncSession,
        terms: list[str],
        top_k: int = 20,
        visibility: str = "public",
        confidence_levels: Optional[list[str]] = None,
        project_ids: Optional[list[uuid.UUID]] = None,
        section_terms: Optional[list[str]] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        if not terms:
            return []

        score = literal(0.0)
        for term in terms:
            pattern = f"%{term}%"
            score += case((func.coalesce(DocumentChunk.title, "").ilike(pattern), 2.0), else_=0.0)
            score += case((func.coalesce(DocumentChunk.section, "").ilike(pattern), 1.5), else_=0.0)
            score += case((func.coalesce(DocumentChunk.content, "").ilike(pattern), 1.0), else_=0.0)

        lexical_score = score.label("lexical_score")
        stmt = select(DocumentChunk, lexical_score).where(
            DocumentChunk.visibility == visibility,
            lexical_score > 0,
        )
        if confidence_levels:
            stmt = stmt.where(DocumentChunk.confidence.in_(confidence_levels))
        if project_ids:
            stmt = stmt.where(DocumentChunk.project_id.in_(project_ids))
        if section_terms:
            stmt = stmt.where(or_(*[
                func.coalesce(DocumentChunk.section, "").ilike(f"%{term}%")
                for term in section_terms
            ]))
        stmt = stmt.order_by(lexical_score.desc()).limit(top_k)

        result = await session.execute(stmt)
        max_score = max(1.0, len(terms) * 4.5)
        return [
            (chunk, min(1.0, float(raw_score) / max_score))
            for chunk, raw_score in result.all()
        ]

    async def upsert_for_document(
        self, session: AsyncSession, document_id: uuid.UUID, chunks: list[dict]
    ) -> None:
        await self.delete_by_document_id(session, document_id)
        for chunk in chunks:
            chunk["document_id"] = document_id
            session.add(DocumentChunk(**chunk))
        await session.commit()

    async def delete_by_document_id(
        self, session: AsyncSession, document_id: uuid.UUID
    ) -> None:
        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        await session.commit()

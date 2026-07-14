import uuid
from typing import Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector
from sqlalchemy import cast, func
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
    ) -> list[tuple[DocumentChunk, float]]:
        query_vec = cast(embedding, Vector(settings.embedding_dimensions))
        cosine_distance = DocumentChunk.embedding.op("<=>")(query_vec)
        stmt = select(
            DocumentChunk,
            cosine_distance.label("cosine_distance"),
        ).where(
            DocumentChunk.visibility == visibility,
            DocumentChunk.embedding.is_not(None),
        )
        if confidence_levels:
            stmt = stmt.where(DocumentChunk.confidence.in_(confidence_levels))
        stmt = stmt.order_by(cosine_distance).limit(top_k)
        result = await session.execute(stmt)
        return [(chunk, float(distance)) for chunk, distance in result.all()]

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

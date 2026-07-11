from typing import Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from app.models.document import Document


class DocumentRepository:
    async def get_by_source_id(self, session: AsyncSession, source_id: str) -> Optional[Document]:
        result = await session.execute(
            select(Document).where(Document.source_id == source_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, session: AsyncSession, data: dict) -> Document:
        stmt = (
            insert(Document)
            .values(**data)
            .on_conflict_do_update(
                index_elements=["source_id"],
                set_={k: v for k, v in data.items() if k != "source_id"},
            )
            .returning(Document)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one()

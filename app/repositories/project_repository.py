import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project


class ProjectRepository:
    async def get_all_public(self, session: AsyncSession) -> list[Project]:
        result = await session.execute(
            select(Project)
            .where(Project.visibility == "public")
            .order_by(Project.sort_order.asc(), Project.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_slug(self, session: AsyncSession, slug: str) -> Optional[Project]:
        result = await session.execute(
            select(Project).where(
                Project.slug == slug,
                Project.visibility == "public",
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, session: AsyncSession, id: uuid.UUID) -> Optional[Project]:
        result = await session.execute(
            select(Project).where(Project.id == id)
        )
        return result.scalar_one_or_none()

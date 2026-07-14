from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.visitor_session import VisitorSession


@dataclass(frozen=True)
class VisitorContext:
    id: uuid.UUID
    new_token: str | None = None


class VisitorSessionService:
    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def get_existing(
        self, request: Request, session: AsyncSession
    ) -> VisitorContext | None:
        settings = get_settings()
        token = request.cookies.get(settings.visitor_cookie_name)
        if not token:
            return None
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(VisitorSession).where(
                VisitorSession.token_hash == self._hash_token(token),
                VisitorSession.revoked_at.is_(None),
                VisitorSession.expires_at > now,
            )
        )
        visitor = result.scalar_one_or_none()
        if visitor is None:
            return None
        last_seen = visitor.last_seen_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        if now - last_seen >= timedelta(hours=1):
            visitor.last_seen_at = now
            await session.commit()
        return VisitorContext(id=visitor.id)

    async def create(self, session: AsyncSession) -> VisitorContext:
        settings = get_settings()
        now = datetime.now(timezone.utc)
        new_token = secrets.token_urlsafe(32)
        visitor = VisitorSession(
            id=uuid.uuid4(),
            token_hash=self._hash_token(new_token),
            expires_at=now + timedelta(days=settings.visitor_session_days),
        )
        session.add(visitor)
        await session.commit()
        return VisitorContext(id=visitor.id, new_token=new_token)

    async def resolve(
        self, request: Request, session: AsyncSession
    ) -> VisitorContext:
        existing = await self.get_existing(request, session)
        return existing or await self.create(session)

    @staticmethod
    def set_cookie(response: Response, context: VisitorContext) -> None:
        if not context.new_token:
            return
        settings = get_settings()
        response.set_cookie(
            key=settings.visitor_cookie_name,
            value=context.new_token,
            max_age=settings.visitor_session_days * 24 * 60 * 60,
            httponly=True,
            secure=settings.app_env == "production",
            samesite="lax",
            path="/",
        )


visitor_session_service = VisitorSessionService()

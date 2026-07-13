import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.feedback import QuestionFeedback


class ConversationRepository:
    async def get_or_create(
        self, session: AsyncSession, session_id: str
    ) -> Conversation:
        stmt = select(Conversation).where(Conversation.session_id == session_id)
        result = await session.execute(stmt)
        conv = result.scalar_one_or_none()
        if conv is None:
            conv = Conversation(session_id=session_id)
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
        return conv

    async def get_recent_messages(
        self, session: AsyncSession, conversation_id: uuid.UUID, limit: int = 6
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def save_message(self, session: AsyncSession, data: dict) -> Message:
        msg = Message(**data)
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg

    async def save_feedback(
        self, session: AsyncSession, data: dict
    ) -> QuestionFeedback:
        stmt = select(QuestionFeedback).where(
            QuestionFeedback.message_id == data["message_id"]
        )
        result = await session.execute(stmt)
        fb = result.scalar_one_or_none()
        if fb is None:
            fb = QuestionFeedback(**data)
            session.add(fb)
        else:
            fb.rating = data["rating"]
            fb.reason = data.get("reason")
            fb.comment = data.get("comment")
        await session.commit()
        await session.refresh(fb)
        return fb

    async def message_belongs_to_conversation(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> bool:
        stmt = select(Message.id).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def touch_conversation(
        self, session: AsyncSession, conversation_id: uuid.UUID
    ) -> None:
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await session.execute(stmt)
        conv = result.scalar_one_or_none()
        if conv:
            conv.last_active_at = datetime.utcnow()
            await session.commit()

    async def delete_expired(
        self, session: AsyncSession, retention_days: int
    ) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        conversation_ids = select(Conversation.id).where(
            Conversation.last_active_at < cutoff
        )
        message_ids = select(Message.id).where(
            Message.conversation_id.in_(conversation_ids)
        )
        await session.execute(
            delete(QuestionFeedback).where(
                QuestionFeedback.message_id.in_(message_ids)
            )
        )
        await session.execute(
            delete(Message).where(Message.conversation_id.in_(conversation_ids))
        )
        result = await session.execute(
            delete(Conversation).where(Conversation.id.in_(conversation_ids))
        )
        await session.commit()
        return result.rowcount or 0

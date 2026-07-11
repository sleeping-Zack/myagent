import uuid
from datetime import datetime
from sqlalchemy import select
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
        fb = QuestionFeedback(**data)
        session.add(fb)
        await session.commit()
        await session.refresh(fb)
        return fb

    async def touch_conversation(
        self, session: AsyncSession, conversation_id: uuid.UUID
    ) -> None:
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await session.execute(stmt)
        conv = result.scalar_one_or_none()
        if conv:
            conv.last_active_at = datetime.utcnow()
            await session.commit()

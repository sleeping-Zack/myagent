from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.feedback import QuestionFeedback
from app.models.message import Message
from app.models.visitor_session import VisitorSession


class ConversationRepository:
    async def create_conversation(
        self,
        session: AsyncSession,
        visitor_id: uuid.UUID,
        title: str | None = None,
    ) -> Conversation:
        conversation_id = uuid.uuid4()
        conversation = Conversation(
            id=conversation_id,
            session_id=str(conversation_id),
            visitor_id=visitor_id,
            title=(title or "新对话").strip()[:120],
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

    async def list_owned(
        self, session: AsyncSession, visitor_id: uuid.UUID, limit: int = 30
    ) -> list[tuple[Conversation, str | None]]:
        latest_preview = (
            select(Message.content)
            .where(Message.conversation_id == Conversation.id)
            .order_by(Message.sequence_no.desc())
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            select(Conversation, latest_preview.label("last_message_preview"))
            .where(
                Conversation.visitor_id == visitor_id,
                Conversation.deleted_at.is_(None),
            )
            .order_by(
                Conversation.last_message_at.desc().nullslast(),
                Conversation.created_at.desc(),
            )
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_owned(
        self,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        visitor_id: uuid.UUID,
    ) -> Conversation | None:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.visitor_id == visitor_id,
                Conversation.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_messages(
        self,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        limit: int = 30,
        before_sequence: int | None = None,
        completed_only: bool = False,
    ) -> list[Message]:
        conditions = [Message.conversation_id == conversation_id]
        if before_sequence is not None:
            conditions.append(Message.sequence_no < before_sequence)
        if completed_only:
            conditions.append(Message.status == "completed")
        stmt = (
            select(Message)
            .where(*conditions)
            .order_by(Message.sequence_no.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def rename(
        self, session: AsyncSession, conversation: Conversation, title: str
    ) -> None:
        conversation.title = title.strip()[:120]
        await session.commit()

    async def soft_delete(
        self, session: AsyncSession, conversation: Conversation
    ) -> None:
        conversation.deleted_at = datetime.now(timezone.utc)
        conversation.status = "deleted"
        conversation.active_generation_id = None
        conversation.generation_started_at = None
        await session.commit()

    async def try_start_generation(
        self,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        visitor_id: uuid.UUID,
        generation_id: uuid.UUID,
    ) -> bool:
        stale_before = datetime.now(timezone.utc) - timedelta(minutes=2)
        stmt = (
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.visitor_id == visitor_id,
                Conversation.deleted_at.is_(None),
                or_(
                    Conversation.active_generation_id.is_(None),
                    Conversation.generation_started_at < stale_before,
                ),
            )
            .values(
                active_generation_id=generation_id,
                generation_started_at=datetime.now(timezone.utc),
            )
            .returning(Conversation.id)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one_or_none() is not None

    async def finish_generation(
        self,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        generation_id: uuid.UUID,
    ) -> None:
        await session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.active_generation_id == generation_id,
            )
            .values(active_generation_id=None, generation_started_at=None)
        )
        await session.commit()

    async def create_message(
        self,
        session: AsyncSession,
        conversation: Conversation,
        *,
        role: str,
        content: str,
        status: str,
        client_message_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
    ) -> Message:
        result = await session.execute(
            select(func.coalesce(func.max(Message.sequence_no), 0)).where(
                Message.conversation_id == conversation.id
            )
        )
        sequence_no = int(result.scalar_one() or 0) + 1
        message = Message(
            id=message_id or uuid.uuid4(),
            conversation_id=conversation.id,
            sequence_no=sequence_no,
            client_message_id=client_message_id,
            role=role,
            content=content,
            status=status,
            citation_ids=[],
            citation_data=[],
        )
        session.add(message)
        conversation.message_count = (conversation.message_count or 0) + 1
        conversation.last_message_at = datetime.now(timezone.utc)
        conversation.last_active_at = datetime.now(timezone.utc)
        if role == "user" and (not conversation.title or conversation.title == "新对话"):
            conversation.title = content.strip().replace("\n", " ")[:40] or "新对话"
        await session.commit()
        await session.refresh(message)
        return message

    async def find_client_message(
        self,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        client_message_id: uuid.UUID,
    ) -> Message | None:
        result = await session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.client_message_id == client_message_id,
            )
        )
        return result.scalar_one_or_none()

    async def complete_assistant_message(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        *,
        content: str,
        status: str,
        citation_ids: list[str] | None = None,
        citation_data: list[dict] | None = None,
        model_name: str | None = None,
        estimated_input_tokens: int | None = None,
        estimated_output_tokens: int | None = None,
        latency_ms: int | None = None,
    ) -> None:
        await session.execute(
            update(Message)
            .where(Message.id == message_id)
            .values(
                content=content,
                status=status,
                citation_ids=citation_ids or [],
                citation_data=citation_data or [],
                model_name=model_name,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                latency_ms=latency_ms,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    async def update_memory(
        self,
        session: AsyncSession,
        conversation: Conversation,
        summary: str,
        through_sequence: int,
    ) -> None:
        conversation.summary = summary
        conversation.summarized_through_sequence = through_sequence
        await session.commit()

    async def save_feedback(
        self, session: AsyncSession, data: dict
    ) -> QuestionFeedback:
        result = await session.execute(
            select(QuestionFeedback).where(
                QuestionFeedback.message_id == data["message_id"]
            )
        )
        feedback = result.scalar_one_or_none()
        if feedback is None:
            feedback = QuestionFeedback(**data)
            session.add(feedback)
        else:
            feedback.rating = data["rating"]
            feedback.reason = data.get("reason")
            feedback.comment = data.get("comment")
        await session.commit()
        await session.refresh(feedback)
        return feedback

    async def message_belongs_to_conversation(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        conversation_id: uuid.UUID,
        visitor_id: uuid.UUID | None = None,
    ) -> bool:
        stmt = select(Message.id).join(Conversation).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
            Conversation.deleted_at.is_(None),
        )
        if visitor_id is not None:
            stmt = stmt.where(Conversation.visitor_id == visitor_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def delete_expired(
        self, session: AsyncSession, retention_days: int
    ) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        expired_conversations = select(Conversation.id).where(
            Conversation.last_active_at < cutoff
        )
        result = await session.execute(
            delete(Conversation).where(Conversation.id.in_(expired_conversations))
        )
        await session.execute(
            delete(VisitorSession).where(
                or_(
                    VisitorSession.expires_at < datetime.now(timezone.utc),
                    VisitorSession.revoked_at.is_not(None),
                )
            )
        )
        await session.commit()
        return result.rowcount or 0

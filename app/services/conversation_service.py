import uuid
from app.repositories.conversation_repository import ConversationRepository
from sqlalchemy.ext.asyncio import AsyncSession


class ConversationService:
    def __init__(self, conv_repo: ConversationRepository, session: AsyncSession) -> None:
        self._repo = conv_repo
        self._session = session

    async def get_or_create(self, session_id: str) -> str:
        conv = await self._repo.get_or_create(self._session, session_id)
        return str(conv.id)

    async def get_context(self, conversation_id: str, last_n: int = 6) -> list[dict]:
        if not conversation_id:
            return []
        messages = await self._repo.get_recent_messages(
            self._session, uuid.UUID(conversation_id), limit=last_n
        )
        return [{"role": m.role, "content": m.content} for m in messages]

    async def save_exchange(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        citation_ids: list[str],
        model_name: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        latency_ms: int,
    ) -> str:
        conv_uuid = uuid.UUID(conversation_id)
        # 确保 conversation 记录存在（用 conversation_id 作为 session_id）
        from sqlalchemy import select
        from app.models.conversation import Conversation
        result = await self._session.execute(
            select(Conversation).where(Conversation.id == conv_uuid)
        )
        if result.scalar_one_or_none() is None:
            self._session.add(Conversation(id=conv_uuid, session_id=conversation_id))
            await self._session.commit()

        await self._repo.save_message(
            self._session,
            {
                "conversation_id": conv_uuid,
                "role": "user",
                "content": question,
                "citation_ids": [],
                "model_name": None,
                "estimated_input_tokens": None,
                "estimated_output_tokens": None,
                "latency_ms": None,
            },
        )

        msg = await self._repo.save_message(
            self._session,
            {
                "conversation_id": conv_uuid,
                "role": "assistant",
                "content": answer,
                "citation_ids": citation_ids,
                "model_name": model_name,
                "estimated_input_tokens": estimated_input_tokens,
                "estimated_output_tokens": estimated_output_tokens,
                "latency_ms": latency_ms,
            },
        )

        await self._repo.touch_conversation(self._session, conv_uuid)
        return str(msg.id)

    async def check_rate_limit(self, session_id: str) -> bool:
        """返回 True 表示已超限（超过 20 轮 = 40 条消息）。"""
        from sqlalchemy import select, func
        from app.models.conversation import Conversation
        from app.models.message import Message

        stmt = select(Conversation).where(Conversation.session_id == session_id)
        result = await self._session.execute(stmt)
        conv = result.scalar_one_or_none()
        if conv is None:
            return False

        count_stmt = (
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conv.id)
        )
        count_result = await self._session.execute(count_stmt)
        count = count_result.scalar_one()
        return count >= 40

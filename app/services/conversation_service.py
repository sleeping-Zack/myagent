from dataclasses import dataclass
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories.conversation_repository import ConversationRepository


@dataclass(frozen=True)
class ConversationMemory:
    summary: str
    recent_messages: list[dict[str, str]]


def _estimate_tokens(text: str) -> int:
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    non_cjk = re.sub(r"[\u3400-\u9fff]", " ", text)
    return cjk + sum(max(1, (len(part) + 3) // 4) for part in non_cjk.split())


def _summary_line(message: Message) -> str:
    role = "用户" if message.role == "user" else "助手"
    content = " ".join(message.content.split())
    if len(content) > 240:
        content = content[:237] + "..."
    return f"{role}：{content}"


class ConversationService:
    def __init__(
        self, repository: ConversationRepository, session: AsyncSession
    ) -> None:
        self._repository = repository
        self._session = session

    async def build_memory(
        self, conversation: Conversation
    ) -> ConversationMemory:
        settings = get_settings()
        messages = await self._repository.get_messages(
            self._session,
            conversation.id,
            limit=200,
            completed_only=True,
        )

        recent_limit = settings.memory_recent_message_limit
        older_messages = messages[:-recent_limit] if len(messages) > recent_limit else []
        recent_messages = messages[-recent_limit:]

        unsummarized = [
            message
            for message in older_messages
            if (message.sequence_no or 0) > conversation.summarized_through_sequence
        ]
        summary = conversation.summary or ""
        if unsummarized:
            appended = "\n".join(_summary_line(message) for message in unsummarized)
            summary = "\n".join(part for part in [summary, appended] if part).strip()
            if len(summary) > settings.memory_summary_max_chars:
                summary = summary[:600] + "\n…\n" + summary[-(settings.memory_summary_max_chars - 603):]
            await self._repository.update_memory(
                self._session,
                conversation,
                summary,
                unsummarized[-1].sequence_no or 0,
            )

        selected: list[Message] = []
        used_tokens = 0
        for message in reversed(recent_messages):
            estimated = _estimate_tokens(message.content)
            if selected and used_tokens + estimated > settings.memory_recent_token_budget:
                break
            selected.append(message)
            used_tokens += estimated
        selected.reverse()

        return ConversationMemory(
            summary=summary,
            recent_messages=[
                {"role": message.role, "content": message.content}
                for message in selected
            ],
        )

from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import uuid

import pytest
from starlette.responses import Response

from app.core.rate_limit import ChatRateLimiter
from app.services.conversation_service import ConversationService
from app.services.visitor_session_service import VisitorContext, VisitorSessionService


def test_memory_summarizes_old_messages_and_keeps_recent(monkeypatch):
    settings = SimpleNamespace(
        memory_recent_message_limit=8,
        memory_recent_token_budget=2500,
        memory_summary_max_chars=4000,
    )
    monkeypatch.setattr(
        "app.services.conversation_service.get_settings", lambda: settings
    )
    messages = [
        SimpleNamespace(sequence_no=index, role="user" if index % 2 else "assistant", content=f"消息 {index}")
        for index in range(1, 11)
    ]
    repository = SimpleNamespace(
        get_messages=AsyncMock(return_value=messages),
        update_memory=AsyncMock(),
    )
    conversation = SimpleNamespace(
        id=uuid.uuid4(), summary=None, summarized_through_sequence=0
    )

    memory = asyncio.run(
        ConversationService(repository, AsyncMock()).build_memory(conversation)
    )

    assert len(memory.recent_messages) == 8
    assert memory.recent_messages[0]["content"] == "消息 3"
    assert "消息 1" in memory.summary
    assert "消息 2" in memory.summary
    repository.update_memory.assert_awaited_once()
    assert repository.update_memory.await_args.args[-1] == 2


@pytest.mark.asyncio
async def test_ip_guard_can_skip_global_daily_budget():
    limiter = ChatRateLimiter()

    assert await limiter.allow("ip:a", 30, 1, count_daily=False)
    assert await limiter.allow("visitor:a", 5, 1)
    assert not await limiter.allow("visitor:b", 5, 1)


def test_visitor_cookie_is_httponly_and_token_hash_is_one_way(monkeypatch):
    settings = SimpleNamespace(
        visitor_cookie_name="hr_session",
        visitor_session_days=30,
        app_env="development",
    )
    monkeypatch.setattr(
        "app.services.visitor_session_service.get_settings", lambda: settings
    )
    raw_token = "browser-secret"
    response = Response()

    VisitorSessionService.set_cookie(
        response, VisitorContext(id=uuid.uuid4(), new_token=raw_token)
    )

    cookie = response.headers["set-cookie"]
    assert raw_token in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert VisitorSessionService._hash_token(raw_token) != raw_token

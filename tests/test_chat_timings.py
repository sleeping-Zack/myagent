import asyncio
import importlib
import json
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

from starlette.requests import Request

from app.schemas.chat import ChatRequest


def test_chat_done_event_exposes_end_to_end_timings(monkeypatch):
    chat_module = importlib.import_module("app.api.chat")
    visitor = SimpleNamespace(id=uuid4())
    conversation = SimpleNamespace(id=uuid4(), message_count=0)
    assistant_message = SimpleNamespace(id=uuid4())

    class RepositoryStub:
        create_conversation = AsyncMock(return_value=conversation)
        try_start_generation = AsyncMock(return_value=True)
        find_client_message = AsyncMock(return_value=None)
        create_message = AsyncMock()
        complete_assistant_message = AsyncMock()
        finish_generation = AsyncMock()

    repository = RepositoryStub()
    repository.create_message.side_effect = [SimpleNamespace(id=uuid4()), assistant_message]
    memory = SimpleNamespace(recent_messages=[], summary="")

    monkeypatch.setattr(chat_module, "ConversationRepository", lambda: repository)
    monkeypatch.setattr(
        chat_module,
        "ConversationService",
        lambda *args: SimpleNamespace(build_memory=AsyncMock(return_value=memory)),
    )
    monkeypatch.setattr(
        chat_module.visitor_session_service,
        "get_existing",
        AsyncMock(return_value=visitor),
    )
    monkeypatch.setattr(
        chat_module.visitor_session_service,
        "set_cookie",
        lambda *args: None,
    )
    monkeypatch.setattr(chat_module.chat_rate_limiter, "allow", AsyncMock(return_value=True))
    monkeypatch.setattr(chat_module.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(
        chat_module.time,
        "perf_counter",
        MagicMock(side_effect=[100.0, 100.5]),
    )
    completed_log = MagicMock()
    monkeypatch.setattr(chat_module.logger, "info", completed_log)

    request = Request({
        "type": "http",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "scheme": "http",
        "server": ("127.0.0.1", 8000),
    })

    async def collect_body():
        response = await chat_module.chat(
            request,
            ChatRequest(question="你好"),
            db=AsyncMock(),
            embedding_svc=SimpleNamespace(),
            deepseek_svc=SimpleNamespace(),
        )
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    body = asyncio.run(collect_body())
    events = body.split("\n\n")
    done_event = next(event for event in events if event.startswith("event: done"))
    data_line = next(line for line in done_event.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))

    assert payload["timings"]["retrieval_ms"] is None
    assert payload["timings"]["llm_ttft_ms"] is None
    assert payload["timings"]["llm_stream_ms"] is None
    assert payload["timings"]["total_ms"] == 500
    completed_log.assert_called_once_with(
        "chat_generation_completed",
        conversation_id=str(conversation.id),
        generation_id=ANY,
        model_name="static-greeting",
        **payload["timings"],
    )

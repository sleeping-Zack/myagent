from datetime import datetime, timedelta, timezone
import json

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.core.rate_limit import ChatRateLimiter
from app.schemas.chat import ChatRequest
from app.services.citation_service import CitationService


def test_conversation_id_must_be_uuid():
    with pytest.raises(ValidationError):
        ChatRequest(question="继续介绍", conversation_id="not-a-uuid")


def test_rate_limiter_enforces_minute_limit():
    limiter = ChatRateLimiter()
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)

    assert limiter.allow("client", 2, 10, now)
    assert limiter.allow("client", 2, 10, now + timedelta(seconds=1))
    assert not limiter.allow("client", 2, 10, now + timedelta(seconds=2))
    assert limiter.allow("client", 2, 10, now + timedelta(seconds=61))


def test_rate_limiter_enforces_daily_limit():
    limiter = ChatRateLimiter()
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)

    assert limiter.allow("client-a", 5, 2, now)
    assert limiter.allow("client-b", 5, 2, now)
    assert not limiter.allow("client-c", 5, 2, now)
    assert limiter.allow("client-c", 5, 2, now + timedelta(days=1))


def test_citation_exposes_ranking_score_not_relevance_percentage():
    citation = CitationService().format_citations([
        {
            "chunk_id": "chunk-1",
            "title": "项目资料",
            "section": "overview",
            "content": "资料内容",
            "score": 0.8123,
            "tags": [],
            "project_id": None,
        }
    ])[0]

    assert citation.ranking_score == 0.8123


def test_global_error_response_does_not_expose_traceback():
    from app.main import global_exception_handler

    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/broken",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
        "scheme": "http",
    })

    import asyncio
    response = asyncio.run(global_exception_handler(request, RuntimeError("secret path")))
    payload = json.loads(response.body)

    assert response.status_code == 500
    assert payload["error"] == "服务暂时不可用"
    assert payload["request_id"]
    assert b"secret path" not in response.body
    assert b"Traceback" not in response.body

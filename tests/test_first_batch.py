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


@pytest.mark.asyncio
async def test_rate_limiter_enforces_minute_limit():
    limiter = ChatRateLimiter()
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)

    assert await limiter.allow("client", 2, 10, now)
    assert await limiter.allow("client", 2, 10, now + timedelta(seconds=1))
    assert not await limiter.allow("client", 2, 10, now + timedelta(seconds=2))
    assert await limiter.allow("client", 2, 10, now + timedelta(seconds=61))


@pytest.mark.asyncio
async def test_rate_limiter_enforces_daily_limit():
    limiter = ChatRateLimiter()
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)

    assert await limiter.allow("client-a", 5, 2, now)
    assert await limiter.allow("client-b", 5, 2, now)
    assert not await limiter.allow("client-c", 5, 2, now)
    assert await limiter.allow("client-c", 5, 2, now + timedelta(days=1))


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


def test_citation_does_not_expose_source_filename():
    citation = CitationService().format_citations([
        {
            "chunk_id": "chunk-1",
            "title": "候选人优势",
            "source_name": "06_hr_interview_qa.md",
            "section": "overview",
            "content": "使用 MASTER_ALL.md 和 projects/ 目录导入资料",
            "score": 0.8,
            "tags": [],
            "project_id": None,
        }
    ])[0]

    assert citation.title == "候选人优势"
    assert "06_hr_interview_qa.md" not in citation.model_dump_json()
    assert "MASTER_ALL.md" not in citation.content_preview
    assert "projects/" not in citation.content_preview


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

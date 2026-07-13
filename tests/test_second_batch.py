import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas.chat import FeedbackRequest
from app.services.deepseek_service import get_deepseek_service
from app.services.embedding_service import get_embedding_service


ROOT = Path(__file__).resolve().parents[1]


def test_sse_parser_handles_fragmented_frames():
    result = subprocess.run(
        ["node", str(ROOT / "tests" / "test_sse_parser.js")],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "sse_parser_ok" in result.stdout


def test_feedback_requires_valid_rating_and_conversation():
    request = FeedbackRequest(conversation_id=uuid4(), rating=1)
    assert request.rating == 1

    with pytest.raises(ValidationError):
        FeedbackRequest(conversation_id=uuid4(), rating=0)


def test_service_factories_reuse_clients():
    assert get_embedding_service() is get_embedding_service()
    assert get_deepseek_service() is get_deepseek_service()


def test_live_health_and_security_headers():
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    csp = response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp
    assert "'unsafe-inline'" not in csp
    assert "script-src 'self' 'nonce-" in csp


def test_golden_set_matches_current_profile():
    cases = json.loads(
        (ROOT / "tests" / "rag_golden_set.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(cases, ensure_ascii=False)

    assert len(cases) == 18
    assert len({case["id"] for case in cases}) == len(cases)
    assert "UNISOC" not in serialized
    assert "OpenHarmony" not in serialized
    assert all(case["expected_sources"] for case in cases)

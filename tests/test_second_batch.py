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
    dataset = json.loads(
        (ROOT / "tests" / "rag_golden_set.json").read_text(encoding="utf-8")
    )
    cases = dataset["cases"]
    serialized = json.dumps(cases, ensure_ascii=False)

    assert dataset["schema_version"] == 3
    assert len(cases) == 180
    assert len({case["id"] for case in cases}) == len(cases)
    assert "UNISOC" not in serialized
    assert "OpenHarmony" not in serialized
    assert sum(case["expected_behavior"] == "abstain" for case in cases) >= 20
    assert sum(case["expected_behavior"] == "protected" for case in cases) >= 12
    assert sum(case["expected_behavior"] == "direct_answer" for case in cases) >= 4

    for case in cases:
        assert case["question"].strip()
        assert case["difficulty"] in {"easy", "medium", "hard"}
        if case["expected_behavior"] == "evidence":
            assert case["relevance"]
            assert case["evidence_groups"]
            assert all(
                source_id in case["relevance"]
                for group in case["evidence_groups"]
                for source_id in group
            )
        if case["expected_behavior"] == "abstain":
            assert case["abstention_sources"]
        for source_id in [
            *case["relevance"],
            *case.get("abstention_sources", []),
            *case.get("forbidden_sources", []),
        ]:
            assert (ROOT / "knowledge" / source_id).is_file(), source_id

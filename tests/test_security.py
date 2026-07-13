"""
输入校验安全测试：超长问题由 Pydantic 拒绝，空问题返回 SSE 错误。
"""
import json
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# App fixture — Mock 掉数据库依赖
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """创建 TestClient，并将 get_session 替换为 Mock。"""
    mock_session = AsyncMock()
    from app.core.database import get_db
    from app.main import app

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(client: TestClient, question: str):
    return client.post("/api/v1/chat", json={"question": question, "stream": True})


def _sse_has_error(response) -> bool:
    """检查 SSE 是否包含 error 事件和用户可见消息。"""
    has_error_event = "event: error" in response.text
    for line in response.text.splitlines():
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            try:
                obj = json.loads(payload)
                if has_error_event and "message" in obj:
                    return True
            except json.JSONDecodeError:
                pass
    return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_question_too_long(client):
    """超过 500 字符的问题应在进入路由前被拒绝。"""
    long_question = "测" * 501
    response = _post(client, long_question)
    assert response.status_code == 422


def test_empty_question(client):
    """空问题应被拒绝（SSE error 响应）。"""
    response = _post(client, "   ")
    assert _sse_has_error(response), (
        "空问题应在 SSE data 中返回 error 字段"
    )

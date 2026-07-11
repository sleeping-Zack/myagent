"""
输入校验安全测试：超长问题和空问题应被 HTTP 400 拒绝。

chat 端点当前实现返回 SSE StreamingResponse（即使是错误），
而非 HTTP 400。本文件测试的是「带 error 字段的 SSE 响应」行为，
并在注释中说明如何升级为真正的 HTTP 400。

若将来端点改为对非法输入直接返回 HTTP 400，
把断言改为 `assert response.status_code == 400` 即可。
"""
import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# App fixture — Mock 掉数据库依赖
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """创建 TestClient，并将 get_session 替换为 Mock。"""
    # 必须在 import app 之前 patch，否则依赖注入已经绑定真实实现
    mock_session = AsyncMock()

    with patch("app.core.database.get_session", return_value=mock_session):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(client: TestClient, question: str):
    return client.post("/api/v1/chat", json={"question": question, "stream": True})


def _sse_has_error(response) -> bool:
    """从 SSE 文本中提取第一个 data: 行并检查是否含 error 字段。"""
    for line in response.text.splitlines():
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            try:
                obj = json.loads(payload)
                if "error" in obj:
                    return True
            except json.JSONDecodeError:
                pass
    return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_question_too_long(client):
    """超过 500 字符的问题应被拒绝（SSE error 响应）。

    TODO: 若端点升级为 HTTP 400，改为：
        assert response.status_code == 400
    """
    long_question = "测" * 501
    response = _post(client, long_question)
    # 当前实现：返回 200 SSE 但携带 error 字段
    assert _sse_has_error(response), (
        "超长问题应在 SSE data 中返回 error 字段"
    )


def test_empty_question(client):
    """空问题应被拒绝（SSE error 响应）。

    TODO: 若端点升级为 HTTP 400，改为：
        assert response.status_code == 400
    """
    response = _post(client, "   ")
    assert _sse_has_error(response), (
        "空问题应在 SSE data 中返回 error 字段"
    )

"""
输入校验安全测试：超长问题由 Pydantic 拒绝，空问题返回 SSE 错误。
"""
import json
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from starlette.requests import Request

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


@pytest.mark.asyncio
async def test_missing_visitor_cookie_does_not_touch_database():
    from app.services.visitor_session_service import VisitorSessionService

    request = Request({"type": "http", "headers": [], "client": ("203.0.113.10", 1234)})
    session = AsyncMock()

    assert await VisitorSessionService().get_existing(request, session) is None
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_untrusted_peer_cannot_spoof_real_ip():
    from app.core.security import get_client_ip

    request = Request({
        "type": "http",
        "headers": [(b"x-real-ip", b"198.51.100.20")],
        "client": ("203.0.113.10", 1234),
    })

    assert get_client_ip(request) == "203.0.113.10"


def test_trusted_local_proxy_can_supply_real_ip():
    from app.core.security import get_client_ip

    request = Request({
        "type": "http",
        "headers": [(b"x-real-ip", b"198.51.100.20")],
        "client": ("127.0.0.1", 1234),
    })

    assert get_client_ip(request) == "198.51.100.20"


def test_unsafe_production_configuration_is_rejected():
    from app.core.config import Settings

    unsafe = Settings(
        _env_file=None,
        app_env="production",
        site_url="http://example.com",
        secret_key="short",
        database_url="postgresql+asyncpg://user:password@db/app",
    )

    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        unsafe.validate_production()


def test_internal_healthcheck_hosts_remain_allowed_in_production():
    from app.core.config import Settings

    configured = Settings(
        _env_file=None,
        app_env="production",
        site_url="https://agent.example.com",
        allowed_hosts="agent.example.com",
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://user:safe-value@db/app",
    )

    configured.validate_production()
    assert configured.effective_allowed_hosts() == [
        "agent.example.com", "localhost", "127.0.0.1"
    ]

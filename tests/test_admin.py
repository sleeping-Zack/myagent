from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials
from starlette.requests import Request

from app.api.admin import display_question, require_admin, validate_admin_credentials
from app.core.config import Settings


def test_admin_accepts_matching_credentials():
    settings = SimpleNamespace(admin_username="admin", admin_password="secret")
    credentials = HTTPBasicCredentials(username="admin", password="secret")

    assert validate_admin_credentials(credentials, settings)


@pytest.mark.parametrize(
    "credentials",
    [
        None,
        HTTPBasicCredentials(username="wrong", password="secret"),
        HTTPBasicCredentials(username="admin", password="wrong"),
    ],
)
def test_admin_rejects_invalid_credentials(credentials):
    settings = SimpleNamespace(admin_username="admin", admin_password="secret")

    assert not validate_admin_credentials(credentials, settings)


def test_admin_stays_closed_without_password():
    settings = SimpleNamespace(admin_username="admin", admin_password="")

    with pytest.raises(HTTPException) as error:
        validate_admin_credentials(None, settings)

    assert error.value.status_code == 503


def test_admin_failed_logins_are_rate_limited():
    request = Request({
        "type": "http",
        "headers": [],
        "client": ("203.0.113.77", 1234),
    })
    settings = Settings(
        _env_file=None,
        admin_username="admin",
        admin_password="secret",
        admin_failed_login_ip_minute_limit=5,
    )
    wrong = HTTPBasicCredentials(username="admin", password="wrong")

    for _ in range(5):
        with pytest.raises(HTTPException) as error:
            require_admin(request, wrong, settings)
        assert error.value.status_code == 401

    with pytest.raises(HTTPException) as error:
        require_admin(request, wrong, settings)
    assert error.value.status_code == 429


def test_admin_replaces_irrecoverable_legacy_question():
    assert display_question("?? HR ??????????") == "历史问题（原始记录编码异常）"
    assert display_question("为什么适合 Agent 开发？") == "为什么适合 Agent 开发？"

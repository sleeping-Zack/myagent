from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials

from app.api.admin import display_question, require_admin


def test_admin_accepts_matching_credentials():
    settings = SimpleNamespace(admin_username="admin", admin_password="secret")
    credentials = HTTPBasicCredentials(username="admin", password="secret")

    assert require_admin(credentials, settings) is None


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

    with pytest.raises(HTTPException) as error:
        require_admin(credentials, settings)

    assert error.value.status_code == 401
    assert error.value.headers == {
        "WWW-Authenticate": 'Basic realm="Personal Agent Admin"'
    }


def test_admin_stays_closed_without_password():
    settings = SimpleNamespace(admin_username="admin", admin_password="")

    with pytest.raises(HTTPException) as error:
        require_admin(None, settings)

    assert error.value.status_code == 503


def test_admin_replaces_irrecoverable_legacy_question():
    assert display_question("?? HR ??????????") == "历史问题（原始记录编码异常）"
    assert display_question("为什么适合 Agent 开发？") == "为什么适合 Agent 开发？"

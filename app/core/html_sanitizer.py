from __future__ import annotations

from urllib.parse import urlparse

import bleach


ALLOWED_TAGS = {
    "a", "blockquote", "br", "code", "em", "h2", "h3", "h4",
    "li", "ol", "p", "pre", "strong", "ul",
}
ALLOWED_ATTRIBUTES = {"a": ["href", "title", "target", "rel"]}


def safe_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value.strip()
    return None


def sanitize_html(value: str | None) -> str:
    return bleach.clean(
        value or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols={"http", "https"},
        strip=True,
    )

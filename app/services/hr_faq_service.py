import re
from functools import lru_cache
from pathlib import Path
from typing import Optional


_KNOWLEDGE_FILE = Path(__file__).resolve().parents[2] / "knowledge" / "06_hr_interview_qa.md"

_PINNED_QUESTIONS = {
    "请用 HR 视角快速介绍一下朱旭",
    "朱旭目前的求职意向和岗位匹配度是什么",
    "为什么朱旭适合 Agent 应用开发实习",
    "朱旭最有代表性的项目产出是什么",
    "朱旭为什么从嵌入式转向 AI 应用开发",
    "朱旭目前最大的不足是什么，如何补齐",
}

_GREETING_QUESTIONS = {"你好", "您好", "嗨", "hello", "hi"}
_GREETING_ANSWER = (
    "你好！我是朱旭的个人招聘知识 Agent。"
    "你可以问我他的项目经历、技术能力、实习经历或岗位匹配情况。"
)


def _normalize_question(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[？?。.\s]+$", "", text)
    return re.sub(r"\s+", " ", text)


def _compact_question(text: str) -> str:
    return re.sub(r"[\W_]+", "", _normalize_question(text), flags=re.UNICODE).lower()


@lru_cache(maxsize=1)
def _load_hr_faq() -> dict[str, str]:
    if not _KNOWLEDGE_FILE.exists():
        return {}

    content = _KNOWLEDGE_FILE.read_text(encoding="utf-8")
    sections = re.split(r"^##\s+", content, flags=re.MULTILINE)
    faq: dict[str, str] = {}

    for section in sections:
        section = section.strip()
        if not section:
            continue

        title, _, body = section.partition("\n")
        title = _normalize_question(title)
        answer = body.strip()

        if title in _PINNED_QUESTIONS and answer:
            faq[title] = answer

    return faq


def get_pinned_hr_answer(question: str) -> Optional[str]:
    normalized = _normalize_question(question)
    faq = _load_hr_faq()
    if normalized in faq:
        return faq[normalized]

    compact = _compact_question(question)
    for title, answer in faq.items():
        title_compact = _compact_question(title)
        if compact == title_compact:
            return answer
        if min(len(compact), len(title_compact)) >= 10 and (
            compact in title_compact or title_compact in compact
        ):
            return answer

    return None


def get_greeting_answer(question: str) -> Optional[str]:
    if _compact_question(question) in _GREETING_QUESTIONS:
        return _GREETING_ANSWER
    return None

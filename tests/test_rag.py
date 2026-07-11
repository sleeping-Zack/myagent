"""
RagService / CitationService 单元测试。
直接实例化 CitationService，不 Mock。
"""
import pytest
from app.services.citation_service import CitationService


@pytest.fixture
def svc():
    return CitationService()


def _chunk(score: float, content: str = "内容", section: str = "overview", tags=None):
    return {
        "chunk_id": "c1",
        "title": "标题",
        "section": section,
        "content": content,
        "score": score,
        "tags": tags or [],
        "project_id": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_evidence(svc):
    """空片段列表应返回 False。"""
    assert svc.has_sufficient_evidence([], question="你是谁？") is False


def test_low_score_evidence(svc):
    """单个分数 0.3 的片段（低于 min_score=0.45）应返回 False。"""
    chunks = [_chunk(score=0.3)]
    assert svc.has_sufficient_evidence(chunks, question="你有什么经历？") is False


def test_sufficient_evidence(svc):
    """两个分数均为 0.7 的片段应返回 True。"""
    chunks = [_chunk(score=0.7), _chunk(score=0.7)]
    assert svc.has_sufficient_evidence(chunks, question="介绍一下你的项目") is True

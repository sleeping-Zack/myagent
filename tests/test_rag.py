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


def test_single_chunk_above_calibrated_threshold_is_sufficient(svc):
    chunks = [_chunk(score=0.43, content="候选人的核心优势是工程落地能力")]

    assert svc.has_sufficient_evidence(
        chunks,
        question="你的优点是什么",
        min_score=0.40,
    ) is True


def test_internship_evidence_can_be_identified_from_title_or_content(svc):
    chunks = [
        {
            **_chunk(score=0.5, content="参与医疗设备嵌入式软件开发"),
            "title": "5. 实习经历",
        },
        _chunk(score=0.48, content="补充经历信息"),
    ]

    assert svc.has_sufficient_evidence(chunks, question="你有什么实习经历") is True

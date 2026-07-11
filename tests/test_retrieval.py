"""
RetrievalService 单元测试。
使用 Mock 替代真实数据库和 embedding 服务，不依赖外部资源。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.retrieval_service import RetrievalService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_chunk(
    chunk_id="chunk-1",
    title="测试标题",
    section="overview",
    content="这是一段测试内容",
    tags=None,
    project_id=None,
):
    chunk = MagicMock()
    chunk.id = chunk_id
    chunk.title = title
    chunk.section = section
    chunk.content = content
    chunk.tags = tags or []
    chunk.project_id = project_id
    return chunk


@pytest.fixture
def mock_embedding_svc():
    svc = MagicMock()
    svc.embed_query.return_value = [0.1] * 512
    return svc


@pytest.fixture
def mock_chunk_repo():
    return AsyncMock()


@pytest.fixture
def retrieval_svc(mock_chunk_repo, mock_embedding_svc):
    return RetrievalService(
        chunk_repo=mock_chunk_repo,
        embedding_svc=mock_embedding_svc,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_query(retrieval_svc, mock_chunk_repo, mock_embedding_svc):
    """空查询（无匹配 chunk）时应返回空列表。"""
    mock_chunk_repo.search_similar.return_value = []
    mock_session = AsyncMock()

    with patch("asyncio.to_thread", return_value=[0.1] * 512):
        results = await retrieval_svc.retrieve(
            question="",
            session=mock_session,
        )

    assert results == []


@pytest.mark.asyncio
async def test_score_calculation(retrieval_svc, mock_chunk_repo):
    """每个返回结果的 final_score 应在 [0, 1] 范围内。"""
    chunks = [
        _make_chunk(chunk_id=f"c{i}", title=f"标题{i}", content=f"内容{i}")
        for i in range(5)
    ]
    mock_chunk_repo.search_similar.return_value = chunks
    mock_session = AsyncMock()

    with patch("asyncio.to_thread", return_value=[0.1] * 512):
        results = await retrieval_svc.retrieve(
            question="测试问题",
            session=mock_session,
            min_score=0.0,  # 关闭过滤，确保所有 chunk 都返回
        )

    assert len(results) > 0
    for r in results:
        assert 0.0 <= r["score"] <= 1.0, f"score {r['score']} 超出 [0,1] 范围"

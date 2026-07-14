"""
RetrievalService 单元测试。
使用 Mock 替代真实数据库和 embedding 服务，不依赖外部资源。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.project_repository import ProjectRepository
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
    chunk.document_id = None
    return chunk


@pytest.fixture
def mock_embedding_svc():
    svc = MagicMock()
    svc.async_embed_query = AsyncMock(return_value=[0.1] * 512)
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

def test_empty_query(retrieval_svc, mock_chunk_repo, mock_embedding_svc):
    """空查询（无匹配 chunk）时应返回空列表。"""
    mock_chunk_repo.search_similar.return_value = []
    mock_session = AsyncMock()

    import asyncio
    results = asyncio.run(retrieval_svc.retrieve(
        question="",
        session=mock_session,
    ))

    assert results == []


def test_score_calculation(retrieval_svc, mock_chunk_repo):
    """每个返回结果的 final_score 应在 [0, 1] 范围内。"""
    chunks = [
        _make_chunk(chunk_id=f"c{i}", title=f"标题{i}", content=f"内容{i}")
        for i in range(5)
    ]
    mock_chunk_repo.search_similar.return_value = [
        (chunk, 0.1 + i * 0.1) for i, chunk in enumerate(chunks)
    ]
    mock_session = AsyncMock()

    import asyncio
    results = asyncio.run(retrieval_svc.retrieve(
        question="测试问题",
        session=mock_session,
        min_score=0.0,  # 关闭过滤，确保所有 chunk 都返回
    ))

    assert len(results) > 0
    for r in results:
        assert 0.0 <= r["score"] <= 1.0, f"score {r['score']} 超出 [0,1] 范围"


def test_retrieval_score_uses_real_cosine_distance(retrieval_svc, mock_chunk_repo):
    close_chunk = _make_chunk(chunk_id="close", title="相同标题")
    distant_chunk = _make_chunk(chunk_id="distant", title="相同标题")
    mock_chunk_repo.search_similar.return_value = [
        (close_chunk, 0.08),
        (distant_chunk, 0.42),
    ]

    import asyncio
    results = asyncio.run(retrieval_svc.retrieve(
        question="没有标题或标签加分的问题",
        session=AsyncMock(),
        min_score=0.0,
    ))

    scores = {result["chunk_id"]: result["score"] for result in results}
    assert scores["close"] == pytest.approx(1.0 - 0.08)
    assert scores["distant"] == pytest.approx(1.0 - 0.42)
    assert scores["close"] > scores["distant"]


@pytest.mark.asyncio
async def test_chunk_repository_returns_cosine_distance():
    session = AsyncMock()
    query_result = MagicMock()
    chunk = _make_chunk()
    query_result.all.return_value = [(chunk, 0.1234)]
    session.execute.return_value = query_result

    rows = await ChunkRepository().search_similar(
        session=session,
        embedding=[0.1] * 1024,
        top_k=1,
    )

    assert rows == [(chunk, 0.1234)]
    statement = str(session.execute.await_args.args[0])
    assert "<=>" in statement
    assert "AS FLOAT" in statement
    assert "embedding IS NOT NULL" in statement


@pytest.mark.asyncio
async def test_public_project_detail_query_enforces_visibility():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    await ProjectRepository().get_by_slug(session, "private-project")

    statement = session.execute.await_args.args[0]
    assert "projects.visibility" in str(statement)

"""
RetrievalService 单元测试。
使用 Mock 替代真实数据库和 embedding 服务，不依赖外部资源。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.project_repository import ProjectRepository
from app.services.query_planner import QueryPlan, QueryTarget
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
    document_id=None,
):
    chunk = MagicMock()
    chunk.id = chunk_id
    chunk.title = title
    chunk.section = section
    chunk.content = content
    chunk.tags = tags or []
    chunk.project_id = project_id
    chunk.document_id = document_id
    return chunk


@pytest.fixture
def mock_embedding_svc():
    svc = MagicMock()
    svc.async_embed_query = AsyncMock(return_value=[0.1] * 512)
    return svc


@pytest.fixture
def mock_chunk_repo():
    repo = AsyncMock()
    repo.search_lexical.return_value = []
    return repo


@pytest.fixture
def mock_project_repo():
    repo = AsyncMock()
    repo.get_all_public.return_value = []
    return repo


@pytest.fixture
def retrieval_svc(mock_chunk_repo, mock_embedding_svc, mock_project_repo):
    return RetrievalService(
        chunk_repo=mock_chunk_repo,
        embedding_svc=mock_embedding_svc,
        project_repo=mock_project_repo,
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


def test_retrieval_orders_unique_documents_before_a_second_chunk(
    retrieval_svc, mock_chunk_repo
):
    chunks = [
        _make_chunk(chunk_id=f"same-{i}", document_id="document-1")
        for i in range(3)
    ]
    chunks.append(_make_chunk(chunk_id="other", document_id="document-2"))
    mock_chunk_repo.search_similar.return_value = [
        (chunk, 0.05 + index * 0.01) for index, chunk in enumerate(chunks)
    ]
    session = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.__iter__.return_value = []

    import asyncio
    results = asyncio.run(retrieval_svc.retrieve(
        question="测试问题",
        session=session,
        min_score=0.0,
    ))

    assert [result["chunk_id"] for result in results] == ["same-0", "other", "same-1"]


def test_multi_part_query_uses_distinct_documents_for_different_topics(
    retrieval_svc, mock_chunk_repo, mock_embedding_svc
):
    shared = _make_chunk(chunk_id="shared", document_id="shared-document")
    project = _make_chunk(chunk_id="project", document_id="project-document")
    internship = _make_chunk(chunk_id="internship", document_id="internship-document")
    education = _make_chunk(chunk_id="education", document_id="education-document")

    mock_embedding_svc.async_embed_documents = AsyncMock(return_value=[
        [0.1] * 512,
        [0.2] * 512,
        [0.3] * 512,
    ])

    async def search_similar(*, embedding, **_kwargs):
        alternatives = {
            0.1: project,
            0.2: internship,
            0.3: education,
        }
        return [(shared, 0.01), (alternatives[embedding[0]], 0.02)]

    mock_chunk_repo.search_similar.side_effect = search_similar

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question="按时间说明朱旭的教育、实习经历和项目经历。",
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert outcome.plan.intent == "multi_part"
    assert {chunk["chunk_id"] for chunk in outcome.chunks} == {
        "shared",
        "project",
        "internship",
        "education",
    }


def test_project_query_keeps_precise_terms_when_planner_adds_a_section_focus(
    retrieval_svc, mock_chunk_repo, mock_embedding_svc, mock_project_repo
):
    project = MagicMock()
    project.id = "mood-project"
    project.slug = "mood_tracker"
    project.title = "情绪分析日记与 AI 心情助手"
    mock_project_repo.get_all_public.return_value = [project]

    metrics = _make_chunk(
        chunk_id="metrics",
        document_id="metrics-document",
        project_id=project.id,
        content="测试集 430 条，Accuracy 91.86%，Macro-F1 92.08%。",
    )
    generic = _make_chunk(
        chunk_id="generic",
        document_id="generic-document",
        project_id=project.id,
        content="项目完成了传统机器学习分类流程。",
    )

    async def embed_query(text):
        return [0.9] * 512 if "Accuracy" in text else [0.1] * 512

    async def embed_documents(texts):
        return [
            [0.9] * 512 if "Accuracy" in text else [0.1] * 512
            for text in texts
        ]

    async def search_similar(*, embedding, section_terms, **_kwargs):
        if section_terms:
            return [(generic, 0.20)]
        return [(metrics, 0.05)] if embedding[0] == 0.9 else [(generic, 0.20)]

    mock_embedding_svc.async_embed_query.side_effect = embed_query
    mock_embedding_svc.async_embed_documents = AsyncMock(side_effect=embed_documents)
    mock_chunk_repo.search_similar.side_effect = search_similar

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question=(
            "Mood Tracker 的测试集规模和 Accuracy、Macro-F1、Weighted-F1 是多少，"
            "为什么不能外推为开放场景效果？"
        ),
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert outcome.plan.intent == "single_project"
    assert outcome.chunks[0]["chunk_id"] == "metrics"


def test_focused_general_topic_gets_a_small_section_ranking_boost(
    retrieval_svc, mock_chunk_repo
):
    focused = _make_chunk(
        chunk_id="focused",
        document_id="focused-document",
        section="问题定位",
        content="结合日志、配置、调用链和复现步骤定位问题。",
    )
    broad = _make_chunk(
        chunk_id="broad",
        document_id="broad-document",
        section="项目简介",
    )

    async def search_similar(*, section_terms, **_kwargs):
        return [(focused, 0.59)] if section_terms else [(broad, 0.45)]

    mock_chunk_repo.search_similar.side_effect = search_similar

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question="遇到系统问题时，通常怎么定位和验证故障？",
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert outcome.chunks[0]["chunk_id"] == "focused"


def test_general_retrieval_keeps_late_precise_chinese_terms(
    retrieval_svc, mock_chunk_repo, mock_embedding_svc
):
    unrelated = _make_chunk(
        chunk_id="unrelated",
        document_id="unrelated-document",
        content="项目使用 Python 和 FastAPI。",
    )
    policy = _make_chunk(
        chunk_id="policy",
        document_id="policy-document",
        content="不使用精通，应区分有项目实践、熟悉和了解。",
    )
    mock_chunk_repo.search_similar.return_value = [(unrelated, 0.35)]
    mock_embedding_svc.async_embed_documents = AsyncMock(return_value=[
        [0.1] * 512,
        [0.2] * 512,
    ])

    async def search_lexical(*, terms, **_kwargs):
        return [(policy, 0.9)] if "精通" in terms else []

    mock_chunk_repo.search_lexical.side_effect = search_lexical

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question=(
            "为什么不应使用精通来描述朱旭的技术栈，"
            "应该换成哪些更准确的层级表述？"
        ),
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert outcome.chunks[0]["chunk_id"] == "policy"


def test_retrieval_keeps_explicit_year_as_a_lexical_term(
    retrieval_svc, mock_chunk_repo, mock_embedding_svc
):
    unrelated = _make_chunk(
        chunk_id="unrelated",
        document_id="unrelated-document",
        content="候选人有项目和实习经历。",
    )
    timeline = _make_chunk(
        chunk_id="timeline",
        document_id="timeline-document",
        content="2025.09 开始实习，2025.10 开始 Agent 项目。",
    )
    mock_chunk_repo.search_similar.return_value = [(unrelated, 0.35)]
    mock_embedding_svc.async_embed_documents = AsyncMock(return_value=[
        [0.1] * 512,
        [0.2] * 512,
        [0.3] * 512,
    ])

    async def search_lexical(*, terms, **_kwargs):
        return [(timeline, 0.9)] if "2025" in terms else []

    mock_chunk_repo.search_lexical.side_effect = search_lexical

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question="2025 年下半年的实习与项目如何衔接？",
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert outcome.chunks[0]["chunk_id"] == "timeline"


def test_multi_part_query_keeps_limited_second_evidence_per_topic(
    retrieval_svc, mock_chunk_repo, mock_embedding_svc
):
    project_primary = _make_chunk(
        chunk_id="project-primary",
        document_id="project-primary-document",
    )
    project_detail = _make_chunk(
        chunk_id="project-detail",
        document_id="project-detail-document",
    )
    internship_primary = _make_chunk(
        chunk_id="internship-primary",
        document_id="internship-primary-document",
    )
    internship_detail = _make_chunk(
        chunk_id="internship-detail",
        document_id="internship-detail-document",
    )
    mock_embedding_svc.async_embed_documents = AsyncMock(return_value=[
        [0.1] * 512,
        [0.2] * 512,
    ])

    async def search_similar(*, embedding, **_kwargs):
        if embedding[0] == 0.1:
            return [(project_primary, 0.05), (project_detail, 0.06)]
        return [(internship_primary, 0.05), (internship_detail, 0.06)]

    mock_chunk_repo.search_similar.side_effect = search_similar

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question="概括朱旭的项目经历和实习经历，并比较两者。",
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert outcome.plan.intent == "multi_part"
    assert {chunk["chunk_id"] for chunk in outcome.chunks} == {
        "project-primary",
        "project-detail",
        "internship-primary",
        "internship-detail",
    }


def test_multi_project_query_includes_unscoped_synthesis_evidence(
    retrieval_svc, mock_chunk_repo, mock_embedding_svc, mock_project_repo
):
    agent = MagicMock(id="agent-id", slug="agentproject", title="Agentproject")
    myagent = MagicMock(id="myagent-id", slug="myagent", title="Myagent")
    mock_project_repo.get_all_public.return_value = [agent, myagent]
    project_chunks = {
        "agent-id": _make_chunk(
            chunk_id="agent",
            document_id="agent-document",
            project_id="agent-id",
        ),
        "myagent-id": _make_chunk(
            chunk_id="myagent",
            document_id="myagent-document",
            project_id="myagent-id",
        ),
    }
    synthesis = _make_chunk(
        chunk_id="synthesis",
        document_id="synthesis-document",
        content="Agentproject 与 Myagent 的统一技术演进说明。",
    )
    mock_embedding_svc.async_embed_documents = AsyncMock(return_value=[
        [0.1] * 512,
        [0.2] * 512,
    ])
    mock_embedding_svc.async_embed_query = AsyncMock(return_value=[0.3] * 512)

    async def search_similar(*, project_ids, **_kwargs):
        if project_ids is None:
            return [(synthesis, 0.05)]
        return [(project_chunks[project_ids[0]], 0.05)]

    mock_chunk_repo.search_similar.side_effect = search_similar

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question="比较 Agentproject 和 Myagent 的技术方案。",
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert outcome.plan.intent == "multi_project"
    assert "synthesis" in {chunk["chunk_id"] for chunk in outcome.chunks}


def test_multi_part_query_includes_unscoped_synthesis_evidence(
    retrieval_svc, mock_chunk_repo, mock_embedding_svc
):
    project = _make_chunk(
        chunk_id="project",
        document_id="project-document",
    )
    internship = _make_chunk(
        chunk_id="internship",
        document_id="internship-document",
    )
    timeline = _make_chunk(
        chunk_id="timeline",
        document_id="timeline-document",
        content="2025.09 开始实习，2025.10 开始 Agent 项目。",
    )
    mock_embedding_svc.async_embed_documents = AsyncMock(return_value=[
        [0.1] * 512,
        [0.2] * 512,
    ])
    calls = 0

    async def search_similar(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return [(project, 0.05)]
        if calls == 2:
            return [(internship, 0.05)]
        return [(timeline, 0.05)]

    mock_chunk_repo.search_similar.side_effect = search_similar

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question=(
            "2025 年下半年嵌入式实习和可治理 Agent 项目在时间上如何衔接，"
            "它们的性质有何不同？"
        ),
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert outcome.plan.intent == "multi_part"
    assert "timeline" in {chunk["chunk_id"] for chunk in outcome.chunks}


def test_complete_coverage_keeps_section_focused_evidence(
    retrieval_svc, mock_chunk_repo, monkeypatch
):
    focused = _make_chunk(
        chunk_id="focused",
        document_id="focused-document",
        section="实习经历",
    )
    broad_one = _make_chunk(
        chunk_id="broad-one",
        document_id="broad-one-document",
    )
    broad_two = _make_chunk(
        chunk_id="broad-two",
        document_id="broad-two-document",
    )
    plan = QueryPlan(
        intent="general",
        targets=[QueryTarget(
            query="正式公司实习",
            coverage_key="正式公司实习",
            section_terms=("实习经历",),
        )],
        expected_coverage=["正式公司实习"],
        context_limit=2,
        strict_coverage=True,
    )
    monkeypatch.setattr(
        "app.services.retrieval_service.plan_question",
        lambda _question, _projects: plan,
    )

    async def search_similar(*, section_terms, **_kwargs):
        if section_terms:
            return [(focused, 0.55)]
        return [(broad_one, 0.05), (broad_two, 0.06)]

    mock_chunk_repo.search_similar.side_effect = search_similar

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question="指出唯一的正式公司实习。",
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert outcome.chunks[0]["chunk_id"] == "focused"


def test_complete_coverage_orders_each_target_before_repeated_target_evidence(
    retrieval_svc, mock_chunk_repo, mock_embedding_svc, monkeypatch
):
    plan = QueryPlan(
        intent="general",
        targets=[
            QueryTarget(query="目标 A", coverage_key="A"),
            QueryTarget(query="目标 B", coverage_key="B"),
        ],
        expected_coverage=["A", "B"],
        context_limit=4,
        strict_coverage=True,
    )
    monkeypatch.setattr(
        "app.services.retrieval_service.plan_question",
        lambda _question, _projects: plan,
    )
    mock_embedding_svc.async_embed_documents = AsyncMock(return_value=[
        [0.1] * 512,
        [0.2] * 512,
    ])
    chunks = {
        "a-one": _make_chunk(chunk_id="a-one", document_id="a-one-document"),
        "a-two": _make_chunk(chunk_id="a-two", document_id="a-two-document"),
        "b-one": _make_chunk(chunk_id="b-one", document_id="b-one-document"),
        "b-two": _make_chunk(chunk_id="b-two", document_id="b-two-document"),
    }

    async def search_similar(*, embedding, **_kwargs):
        if embedding[0] == 0.1:
            return [(chunks["a-one"], 0.01), (chunks["a-two"], 0.02)]
        return [(chunks["b-one"], 0.20), (chunks["b-two"], 0.21)]

    mock_chunk_repo.search_similar.side_effect = search_similar

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question="同时回答目标 A 和目标 B。",
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert [chunk["coverage_keys"] for chunk in outcome.chunks[:2]] == [
        ["A"],
        ["B"],
    ]


def test_multi_project_results_cover_each_project_before_repeating_one(
    retrieval_svc, mock_chunk_repo, mock_embedding_svc, mock_project_repo
):
    project_specs = [
        ("agent-id", "agentproject", "可治理 Agent 平台", 0.10),
        ("farino-id", "farino", "法奥机器人智能客服平台", 0.20),
        ("myagent-id", "myagent", "朱旭个人招聘知识 Agent", 0.12),
        ("mood-id", "mood_tracker", "情绪分析日记与 AI 心情助手", 0.30),
    ]
    projects = []
    chunks_by_project = {}
    for project_id, slug, title, distance in project_specs:
        project = MagicMock()
        project.id = project_id
        project.slug = slug
        project.title = title
        projects.append(project)
        chunks_by_project[project_id] = [
            (
                _make_chunk(
                    chunk_id=f"{slug}-summary",
                    document_id=f"{slug}-summary-document",
                    project_id=project_id,
                ),
                distance,
            ),
            (
                _make_chunk(
                    chunk_id=f"{slug}-readme",
                    document_id=f"{slug}-readme-document",
                    project_id=project_id,
                ),
                distance + 0.01,
            ),
        ]

    mock_project_repo.get_all_public.return_value = projects

    async def embed_documents(texts):
        return [[0.1] * 512 for _ in texts]

    async def search_similar(*, project_ids, **_kwargs):
        if project_ids is None:
            return []
        return chunks_by_project[project_ids[0]]

    mock_embedding_svc.async_embed_documents = AsyncMock(side_effect=embed_documents)
    mock_chunk_repo.search_similar.side_effect = search_similar

    import asyncio
    outcome = asyncio.run(retrieval_svc.retrieve_with_plan(
        question="请分别介绍四个项目的性质、个人职责和技术重点。",
        session=AsyncMock(),
        top_k=5,
        min_score=0.0,
    ))

    assert outcome.plan.intent == "multi_project"
    assert {chunk["project_slug"] for chunk in outcome.chunks[:4]} == {
        "agentproject",
        "farino",
        "myagent",
        "mood_tracker",
    }


def test_chunk_repository_returns_cosine_distance():
    session = AsyncMock()
    query_result = MagicMock()
    chunk = _make_chunk()
    query_result.all.return_value = [(chunk, 0.1234)]
    session.execute.return_value = query_result

    import asyncio
    rows = asyncio.run(ChunkRepository().search_similar(
        session=session, embedding=[0.1] * 1024, top_k=1,
    ))

    assert rows == [(chunk, 0.1234)]
    statement = str(session.execute.await_args.args[0])
    assert "<=>" in statement
    assert "AS FLOAT" in statement
    assert "embedding IS NOT NULL" in statement


def test_chunk_repository_lexical_search_uses_ranked_text_fields():
    session = AsyncMock()
    query_result = MagicMock()
    chunk = _make_chunk()
    query_result.all.return_value = [(chunk, 4.5)]
    session.execute.return_value = query_result

    import asyncio
    rows = asyncio.run(ChunkRepository().search_lexical(
        session=session, terms=["法奥"], top_k=1,
    ))

    assert rows == [(chunk, 1.0)]
    statement = str(session.execute.await_args.args[0])
    assert "lower" in statement.lower()
    assert "ORDER BY" in statement


def test_chunk_repository_lexical_score_represents_query_term_coverage():
    session = AsyncMock()
    query_result = MagicMock()
    chunk = _make_chunk()
    query_result.all.return_value = [(chunk, 6.0)]
    session.execute.return_value = query_result

    import asyncio
    rows = asyncio.run(ChunkRepository().search_lexical(
        session=session,
        terms=[f"term-{index}" for index in range(12)],
        top_k=1,
    ))

    assert rows == [(chunk, 0.5)]


def test_public_project_detail_query_enforces_visibility():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    import asyncio
    asyncio.run(ProjectRepository().get_by_slug(session, "private-project"))

    statement = session.execute.await_args.args[0]
    assert "projects.visibility" in str(statement)

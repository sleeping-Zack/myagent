import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.query_planner import plan_question
from app.services.retrieval_service import RetrievalService
from scripts.ingest_knowledge import infer_project_slug


def _projects():
    values = [
        ("agentproject", "面向智能硬件客服场景的可治理 Agent 平台"),
        ("farino", "法奥机器人智能客服平台"),
        ("myagent", "朱旭个人招聘知识 Agent"),
        ("mood_tracker", "情绪分析日记与 AI 心情助手"),
    ]
    return [
        SimpleNamespace(id=f"id-{slug}", slug=slug, title=title)
        for slug, title in values
    ]


@pytest.mark.parametrize(
    "question",
    [
        "请列出所有可用项目名称",
        "你做过哪些项目？",
        "目前公开的项目清单是什么？",
        "有哪几个代表性作品？",
        "目前展示过哪些代表性作品？",
    ],
)
def test_project_list_paraphrases_use_structured_route(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "project_list"


def test_all_project_details_are_planned_per_project():
    plan = plan_question("请分别介绍所有项目的背景、职责和技术栈", _projects())

    assert plan.intent == "multi_project"
    assert len(plan.targets) == 12
    assert {target.project_slug for target in plan.targets} == {
        "agentproject", "farino", "myagent", "mood_tracker"
    }
    assert plan.context_limit == 12
    assert all(target.section_terms for target in plan.targets)
    assert len(plan.expected_coverage) == 12


def test_two_named_projects_are_retrieved_independently():
    plan = plan_question("比较法奥机器人和情绪日记项目的技术方案", _projects())

    assert plan.intent == "multi_project"
    assert [target.project_slug for target in plan.targets] == ["farino", "mood_tracker"]


def test_cross_domain_question_is_split_without_becoming_all_projects():
    plan = plan_question("请分别介绍项目、实习经历和技能", _projects())

    assert plan.intent == "multi_part"
    assert plan.expected_coverage == ["项目", "实习经历", "技能"]


def test_unrecognized_complex_clauses_are_still_retrieved_independently():
    plan = plan_question(
        "说明为什么转向 AI；介绍遇到的最大技术难题；再说明未来计划",
        _projects(),
    )

    assert plan.intent == "multi_part"
    assert len(plan.targets) == 3
    assert plan.expected_coverage == [target.coverage_key for target in plan.targets]


def test_single_project_alias_uses_project_filter():
    plan = plan_question("Farino 项目中负责了哪些模块？", _projects())

    assert plan.intent == "single_project"
    assert {target.project_slug for target in plan.targets} == {"farino"}


def test_project_slug_is_inferred_for_main_and_readme_documents():
    from pathlib import Path

    assert infer_project_slug(
        Path("knowledge/projects/farino.md").resolve(), {}
    ) == "farino"
    assert infer_project_slug(
        Path("knowledge/projects/mood_trackerREADME.md").resolve(), {}
    ) == "mood_tracker"


def test_structured_project_list_does_not_call_embedding():
    project_repo = AsyncMock()
    project_repo.get_all_public.return_value = _projects()
    embedding = MagicMock()
    service = RetrievalService(AsyncMock(), embedding, project_repo)

    outcome = asyncio.run(service.retrieve_with_plan(
        "请列出所有可用项目名称",
        session=AsyncMock(),
    ))

    assert outcome.direct_answer is not None
    assert all(project.title in outcome.direct_answer for project in _projects())
    embedding.async_embed_query.assert_not_called()


def test_multi_project_retrieval_tracks_complete_coverage():
    projects = _projects()
    project_repo = AsyncMock()
    project_repo.get_all_public.return_value = projects
    embedding = MagicMock()
    embedding.async_embed_documents = AsyncMock(return_value=[[0.1]] * 8)
    service = RetrievalService(AsyncMock(), embedding, project_repo)

    async def fake_retrieve_target(**kwargs):
        if kwargs["project_ids"] is None:
            return []
        project_id = kwargs["project_ids"][0]
        project = next(item for item in projects if item.id == project_id)
        return [{
            "chunk_id": f"chunk-{project.slug}",
            "title": project.title,
            "section": "项目背景",
            "content": f"{project.title}的项目证据",
            "score": 0.8,
            "tags": ["project"],
            "project_id": project.id,
            "project_slug": project.slug,
        }]

    service._retrieve_target = fake_retrieve_target
    outcome = asyncio.run(service.retrieve_with_plan(
        "请分别介绍所有项目的背景和技术方案",
        session=AsyncMock(),
    ))

    assert len(outcome.chunks) == 4
    assert outcome.missing_coverage == []
    covered = {key for chunk in outcome.chunks for key in chunk["coverage_keys"]}
    assert covered == set(outcome.plan.expected_coverage)


def test_multi_project_retrieval_reports_only_missing_project():
    projects = _projects()
    project_repo = AsyncMock()
    project_repo.get_all_public.return_value = projects
    embedding = MagicMock()
    embedding.async_embed_documents = AsyncMock(return_value=[[0.1]] * 16)
    service = RetrievalService(AsyncMock(), embedding, project_repo)

    async def fake_retrieve_target(**kwargs):
        if kwargs["project_ids"] is None:
            return []
        project_id = kwargs["project_ids"][0]
        project = next(item for item in projects if item.id == project_id)
        if project.slug == "farino":
            return []
        return [{
            "chunk_id": f"chunk-{project.slug}",
            "title": project.title,
            "section": "项目背景",
            "content": "项目证据",
            "score": 0.8,
            "tags": [],
            "project_id": project.id,
            "project_slug": project.slug,
        }]

    service._retrieve_target = fake_retrieve_target
    outcome = asyncio.run(service.retrieve_with_plan(
        "请分别介绍所有项目",
        session=AsyncMock(),
    ))

    assert outcome.missing_coverage
    assert all(
        key.startswith("法奥机器人智能客服平台/")
        for key in outcome.missing_coverage
    )

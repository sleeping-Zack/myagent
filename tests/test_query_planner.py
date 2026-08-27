import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.citation_service import CitationService
from app.services.query_planner import plan_question
from app.services.retrieval_service import RetrievalOutcome, RetrievalService
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


@pytest.mark.parametrize(
    "question",
    [
        "What projects have you built? List their names.",
        "先别展开细节，报一下你现在公开的项目名。",
    ],
)
def test_project_list_supports_english_and_colloquial_requests(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "project_list"


@pytest.mark.parametrize(
    "question",
    [
        "能把你公开作品的名字汇总一下吗？",
        "Could you give me the names of your public projects?",
        "你目前公开展示了什么项目？",
    ],
)
def test_project_list_supports_natural_name_requests(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "project_list"


@pytest.mark.parametrize(
    "question",
    [
        "朱旭在传统机器学习项目中实际使用过哪些评估指标？",
        "长冈血压计项目覆盖多少患者并降低了多少故障率？",
    ],
)
def test_project_attribute_questions_do_not_use_project_list(question):
    plan = plan_question(question, _projects())

    assert plan.intent != "project_list"


@pytest.mark.parametrize(
    "question",
    [
        "这个项目名称为什么要这样设计？",
        "哪些项目管理方法适合三人团队？",
    ],
)
def test_project_list_does_not_match_names_or_management_as_attributes(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "general"


def test_english_project_comparison_does_not_use_project_list():
    plan = plan_question(
        "What projects use RAG, and how do their architectures differ?",
        _projects(),
    )

    assert plan.intent != "project_list"


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


@pytest.mark.parametrize(
    "question",
    [
        "Compare all of your projects by architecture.",
        "逐个说说每项作品采用的后端框架。",
        "比较你做的各个作品的技术路线。",
    ],
)
def test_all_project_comparisons_support_english_and_work_synonyms(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "multi_project"
    assert {target.project_slug for target in plan.targets} == {
        "agentproject",
        "farino",
        "myagent",
        "mood_tracker",
    }


@pytest.mark.parametrize(
    "question",
    [
        "把四个核心项目按个人项目和校企合作分类，并指出唯一的正式公司实习。",
        "逐项判断全部公开项目属于个人还是校企合作，另外说明正式企业实习是哪段经历。",
    ],
)
def test_all_project_nature_plan_also_covers_company_internship(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "multi_project"
    assert {target.project_slug for target in plan.targets if target.project_slug} == {
        "agentproject",
        "farino",
        "myagent",
        "mood_tracker",
    }
    internship_targets = [
        target for target in plan.targets
        if target.coverage_key == "正式公司实习"
    ]
    assert len(internship_targets) == 1
    assert internship_targets[0].project_slug is None
    assert {"经历结构", "经历性质"}.issubset(
        internship_targets[0].section_terms
    )


def test_two_named_projects_are_retrieved_independently():
    plan = plan_question("比较法奥机器人和情绪日记项目的技术方案", _projects())

    assert plan.intent == "multi_project"
    assert [target.project_slug for target in plan.targets] == ["farino", "mood_tracker"]


@pytest.mark.parametrize(
    ("question", "target_count"),
    [
        ("Compare Farino's orchestration with Agentproject's architecture.", 2),
        ("How do Mood Tracker and MyAgent differ in deployment architecture?", 2),
        ("逐个说说每项作品采用的后端框架。", 4),
        ("What architecture does Farino use?", 1),
    ],
)
def test_technology_questions_only_plan_technology_targets(
    question,
    target_count,
):
    plan = plan_question(question, _projects())

    assert len(plan.targets) == target_count
    assert all(
        target.coverage_key.endswith("/技术方案")
        for target in plan.targets
    )


@pytest.mark.parametrize(
    "question",
    [
        "比较 Agentproject 的审批策略和 Farino 的工具参数校验机制。",
        "法奥和个人知识站的流式事件协议如何同步步骤、来源与 token？",
    ],
)
def test_governance_and_streaming_mechanisms_are_technology_fields(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "multi_project"
    assert len(plan.targets) == 2
    assert all(
        target.coverage_key.endswith("/技术方案")
        for target in plan.targets
    )


def test_non_technical_project_result_comparison_stays_out_of_technology():
    plan = plan_question(
        "法奥和情绪日记分别取得了哪些成果？",
        _projects(),
    )

    assert plan.intent == "multi_project"
    assert len(plan.targets) == 2
    assert all(
        target.coverage_key.endswith("/结果与产出")
        for target in plan.targets
    )


def test_project_problem_and_engineering_mechanism_plan_two_fields_per_project():
    plan = plan_question(
        "全部项目各自在解决哪类需求，又采用了什么工程机制？",
        _projects(),
    )

    assert plan.intent == "multi_project"
    assert len(plan.targets) == 8
    assert {
        target.coverage_key.rsplit("/", 1)[-1]
        for target in plan.targets
    } == {"项目背景", "技术方案"}


def test_cross_domain_question_is_split_without_becoming_all_projects():
    plan = plan_question("请分别介绍项目、实习经历和技能", _projects())

    assert plan.intent == "multi_part"
    assert plan.expected_coverage == ["项目", "实习经历", "技能"]


@pytest.mark.parametrize(
    "question",
    [
        "按 2024、2025、2026 三个阶段概括朱旭的获奖、实习和 AI 项目经历。",
        "分年份梳理 2023、2024、2025 的获奖、实习与项目节点。",
    ],
)
def test_yearly_experience_plan_includes_a_timeline_target(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "multi_part"
    timeline_targets = [
        target for target in plan.targets
        if target.coverage_key == "阶段时间线"
    ]
    assert len(timeline_targets) == 1
    assert "经历时间线" in timeline_targets[0].section_terms
    assert "阶段时间线" in plan.expected_coverage


def test_named_project_and_independent_internship_remain_multi_part():
    plan = plan_question(
        "2025 年下半年嵌入式实习和可治理 Agent 项目在时间上如何衔接，它们的性质有何不同？",
        _projects(),
    )

    assert plan.intent == "multi_part"


@pytest.mark.parametrize(
    "question",
    [
        "求职材料中需要区分哪些经历性质、贡献来源和效果口径？",
        "面对纯算法研究岗和 AI 应用后端岗，分别有何匹配与不匹配？",
    ],
)
def test_semantic_multi_part_patterns_do_not_require_clause_delimiters(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "multi_part"


@pytest.mark.parametrize(
    "question",
    [
        "求职介绍里，经历类型、个人贡献以及成果表述要如何保持一致？",
        "研究型算法职位与应用型后端职位，分别有哪些适配点和能力缺口？",
    ],
)
def test_semantic_slots_support_unseen_multi_part_paraphrases(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "multi_part"
    assert len(plan.targets) >= 2


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


@pytest.mark.parametrize(
    ("question", "project_slug"),
    [
        (
            "AgentState 保存哪些请求与执行字段，各状态如何流转？",
            "agentproject",
        ),
        ("动态计划遇到无效工具时有哪些降级措施？", "farino"),
        ("个人知识 Agent 在检索前检查哪些敏感内容模式？", "myagent"),
        ("predict_emotion 返回哪些字段？", "mood_tracker"),
    ],
)
def test_project_specific_components_resolve_to_their_project(
    question,
    project_slug,
):
    plan = plan_question(question, _projects())

    assert plan.intent == "single_project"
    assert {target.project_slug for target in plan.targets} == {project_slug}


def test_cross_project_query_resolves_every_named_project():
    plan = plan_question(
        "Agentproject 与个人知识 Agent 如何分别处理证据不足？",
        _projects(),
    )

    assert plan.intent == "multi_project"
    assert {target.project_slug for target in plan.targets} == {
        "agentproject",
        "myagent",
    }


def test_shared_technology_terms_do_not_select_a_project_by_themselves():
    plan = plan_question("RAG 和 SSE 分别适合解决什么问题？", _projects())

    assert plan.intent == "general"
    assert all(target.project_slug is None for target in plan.targets)


@pytest.mark.parametrize(
    "question",
    [
        "EventBus 是什么设计模式，通常如何解耦模块？",
        "CircuitBreaker 和限流器有什么区别？",
        "joblib 与 pickle 的适用场景有何差异？",
        "pgvector 与 Milvus 应该如何选型？",
        "一个任务目标应当怎样拆解才清晰？",
        "K-Means 的 cluster id 能否直接解释为业务标签？",
    ],
)
def test_weak_component_terms_need_portfolio_context(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "general"
    assert all(target.project_slug is None for target in plan.targets)


@pytest.mark.parametrize(
    ("question", "project_slug"),
    [
        ("你的项目为什么用 joblib 保存训练模型？", "mood_tracker"),
        ("候选人的系统怎样用 CircuitBreaker 保护工具调用？", "agentproject"),
    ],
)
def test_weak_component_terms_resolve_with_portfolio_context(
    question,
    project_slug,
):
    plan = plan_question(question, _projects())

    assert plan.intent == "single_project"
    assert {target.project_slug for target in plan.targets} == {project_slug}


@pytest.mark.parametrize(
    ("question", "project_slug"),
    [
        ("批准或拒绝后，审批记录怎样恢复执行？", "agentproject"),
        ("回答生成时先返回 source，最后怎样保存生成元数据？", "myagent"),
        ("系统加载对话上下文后，会持久化哪些回答信息？", "myagent"),
    ],
)
def test_multiple_weak_signals_resolve_a_project_without_name(
    question,
    project_slug,
):
    plan = plan_question(question, _projects())

    assert plan.intent == "single_project"
    assert {target.project_slug for target in plan.targets} == {project_slug}


def test_project_nature_question_targets_nature_sections():
    plan = plan_question(
        "Farino 是正式 AI 实习、个人项目，还是基于 AIFlowy 的校企合作？",
        _projects(),
    )

    assert plan.intent == "single_project"
    assert plan.targets[0].coverage_key.endswith("/经历性质")
    assert "经历性质" in plan.targets[0].section_terms


@pytest.mark.parametrize(
    ("question", "section"),
    [
        (
            "为什么做过机器学习项目却不能描述成深度学习算法工程师？",
            "机器学习能力边界",
        ),
        ("遇到系统问题时，通常怎么定位和验证故障？", "问题定位"),
        ("在 Agent、RAG 和后端方向有哪些重点技能？", "重点技能"),
    ],
)
def test_general_topics_use_focused_queries(question, section):
    plan = plan_question(question, _projects())

    assert plan.intent == "general"
    assert section in plan.targets[0].section_terms


def test_skill_matrix_topic_is_not_split_by_category_labels():
    plan = plan_question(
        "技能矩阵如何区分重点技能、有项目实践和基础二次开发能力？请各举例。",
        _projects(),
    )

    assert plan.intent == "general"


@pytest.mark.parametrize(
    "question",
    [
        "为什么不应使用精通来描述朱旭的技术栈，应该换成哪些更准确的层级表述？",
        "简历里别写专家级，技术能力应按什么层次来措辞？",
    ],
)
def test_skill_wording_question_covers_boundaries_and_proficiency_levels(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "general"
    assert {target.coverage_key for target in plan.targets} == {
        "技能能力边界",
        "技能措辞层级",
    }
    assert plan.requires_complete_coverage


@pytest.mark.parametrize(
    "question",
    [
        "哪些经历能证明朱旭关注测试、离线评测、Trace 和故障定位？",
        "候选人在自动化测试、离线基准、链路追踪和问题排查方面有哪些实践？",
    ],
)
def test_engineering_evidence_question_plans_each_capability_surface(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "general"
    assert {target.coverage_key for target in plan.targets} == {
        "测试实践",
        "离线评测",
        "Trace 与可观测性",
        "故障定位",
    }
    assert plan.requires_complete_coverage


def test_strict_general_plan_rejects_a_missing_coverage_surface():
    question = "哪些经历能证明候选人关注测试、离线评测和故障定位？"
    plan = plan_question(question, _projects())
    outcome = RetrievalOutcome(
        chunks=[{"score": 0.9, "content": "测试和故障定位实践"}],
        plan=plan,
        missing_coverage=["离线评测"],
    )

    assert plan.requires_complete_coverage
    assert not CitationService().has_sufficient_evidence(outcome, question)


def test_ordinary_general_plan_does_not_require_every_planned_surface():
    question = "遇到系统故障时通常如何定位问题？"
    plan = plan_question(question, _projects())
    outcome = RetrievalOutcome(
        chunks=[{"score": 0.9, "content": "通过日志和复现步骤定位"}],
        plan=plan,
        missing_coverage=["general"],
    )

    assert not plan.requires_complete_coverage
    assert CitationService().has_sufficient_evidence(outcome, question)


@pytest.mark.parametrize(
    "question",
    [
        "公开的一句话介绍同时提到了哪些 AI 应用技术和哪类真实实习背景？",
        "软硬件联调涉及控制板、血压计以及哪些输入输出或反馈模块？",
        "最有代表性的项目产出为什么同时包含检索链路和治理链路？",
    ],
)
def test_conjunction_inside_one_topic_does_not_create_multiple_parts(question):
    plan = plan_question(question, _projects())

    assert plan.intent == "general"


@pytest.mark.parametrize(
    ("question", "project_slug"),
    [
        (
            "BudgetManager 约束哪些资源，reserve、commit 和 release 分别在什么时候发生？",
            "agentproject",
        ),
        (
            "AnswerVerifier 会检查哪些内容，LLM Judge 在其中是什么角色？",
            "agentproject",
        ),
        (
            "Agentproject 做了哪些测试与可观测建设，目前又有哪些明确局限？",
            "agentproject",
        ),
        (
            "从历史客服会话到知识库回流，法奥项目的 QA 数据闭环包含哪些步骤？",
            "farino",
        ),
        (
            "法奥项目如何进行企业内网部署，哪些能力来自个人改造，哪些不能说成从零开发？",
            "farino",
        ),
        (
            "情绪分类项目比较了哪些传统模型，默认模型按什么规则选择？",
            "mood_tracker",
        ),
        (
            "本地情绪模型如何通过 Django 完成预测、入库和趋势展示？",
            "mood_tracker",
        ),
        (
            "Farino 项目实际有多少企业用户、日访问量和正式上线客户？",
            "farino",
        ),
        (
            "Agentproject 在线上生产环境的并发量、SLA 和商业收益分别是多少？",
            "agentproject",
        ),
        (
            "本站项目已有多少真实访问用户，生产稳定性达到几个九？",
            "myagent",
        ),
    ],
)
def test_named_project_detail_questions_do_not_use_project_list(
    question,
    project_slug,
):
    plan = plan_question(question, _projects())

    assert plan.intent == "single_project"
    assert {target.project_slug for target in plan.targets} == {project_slug}


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
    embedding.async_embed_query = AsyncMock(return_value=[0.1])
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
    embedding.async_embed_query = AsyncMock(return_value=[0.1])
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

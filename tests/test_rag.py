"""
RagService / CitationService 单元测试。
直接实例化 CitationService，不 Mock。
"""
import asyncio

import pytest
from app.services.citation_service import CitationService
from app.services.query_planner import QueryPlan
from app.services.rag_service import RagService
from app.services.retrieval_service import RetrievalOutcome


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


def test_multi_project_retrieval_requires_complete_coverage(svc):
    outcome = RetrievalOutcome(
        chunks=[_chunk(score=0.9, content="Agentproject 使用 Chroma 构建知识索引。")],
        plan=QueryPlan(
            intent="multi_project",
            expected_coverage=["agentproject", "myagent"],
        ),
        missing_coverage=["myagent"],
    )

    assert svc.has_sufficient_evidence(
        outcome,
        question="比较 Agentproject 和 Myagent 的知识索引。",
    ) is False


def test_project_list_retrieval_requires_a_structured_direct_answer(svc):
    chunks = [_chunk(score=1.0, content="1. Agentproject\n2. Myagent")]
    plan = QueryPlan(intent="project_list")

    without_answer = RetrievalOutcome(
        chunks=chunks,
        plan=plan,
        missing_coverage=[],
    )
    with_answer = RetrievalOutcome(
        chunks=chunks,
        plan=plan,
        missing_coverage=[],
        direct_answer="目前公开展示 2 个项目：Agentproject、Myagent。",
    )

    assert svc.has_sufficient_evidence(
        without_answer,
        question="请列出公开项目名称。",
    ) is False
    assert svc.has_sufficient_evidence(
        with_answer,
        question="请列出公开项目名称。",
    ) is True


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("项目使用 Python 3.11 和 PostgreSQL 16。", False),
        ("线上每秒请求量和 P95 响应时间均未记录。", False),
        ("线上吞吐为 120 QPS，P95 响应时间为 180ms。", True),
    ],
)
def test_online_throughput_requires_metric_specific_values(svc, content, expected):
    outcome = RetrievalOutcome(
        chunks=[_chunk(score=0.9, content=content)],
        plan=QueryPlan(intent="single_project"),
        missing_coverage=[],
    )

    assert svc.has_sufficient_evidence(
        outcome,
        question="个人知识 Agent 在线上每秒能处理多少请求，P95 响应时间是多少？",
    ) is expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("系统会动态生成 3 到 5 步客服执行计划。", False),
        ("日访问量和日客服请求量均未统计。", False),
        ("日访问量为 2000 次；日客服请求量为 800 次。", True),
    ],
)
def test_daily_operating_volume_requires_each_requested_metric(svc, content, expected):
    chunks = [_chunk(score=0.9, content=content)]

    assert svc.has_sufficient_evidence(
        chunks,
        question="Farino 正式环境每天有多少次访问和客服请求？",
    ) is expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("项目支持 Docker Compose 企业内网部署和 3 到 5 步动态计划。", False),
        ("正式上线企业和客户现场覆盖数量均未记录。", False),
        ("已正式上线到甲公司和乙公司，共覆盖 2 个客户现场。", True),
    ],
)
def test_rollout_scope_requires_enterprise_and_site_values(svc, content, expected):
    chunks = [_chunk(score=0.9, content=content)]

    assert svc.has_sufficient_evidence(
        chunks,
        question="Farino 已正式上线到哪些企业，覆盖了多少客户现场？",
    ) is expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("离线检索集有 30 题，Recall@5 为 93.3%。", False),
        ("真实模型会单独评测，但线上回答正确率尚未记录。", False),
        ("线上回答正确率由 80% 提高到 90%，提升 10 个百分点。", True),
    ],
)
def test_online_accuracy_requires_an_online_metric_value(svc, content, expected):
    chunks = [_chunk(score=0.9, content=content)]

    assert svc.has_sufficient_evidence(
        chunks,
        question="接入真实大模型后，线上回答正确率提高了多少？",
    ) is expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("后续将增加系统化路由评测；动态计划包含 3 到 5 步。", False),
        ("路由准确率尚未统计，测试集规模也未记录。", False),
        ("路由准确率为 92%；测试集规模为 200 条。", True),
    ],
)
def test_routing_accuracy_requires_accuracy_and_test_set_size(svc, content, expected):
    chunks = [_chunk(score=0.9, content=content)]

    assert svc.has_sufficient_evidence(
        chunks,
        question="Farino 的路由准确率是多少，测试集有多大？",
    ) is expected


def test_rag_service_refuses_when_retrieval_coverage_is_incomplete():
    class RetrievalStub:
        async def retrieve_with_plan(self, *args, **kwargs):
            return RetrievalOutcome(
                chunks=[_chunk(score=0.9, content="Agentproject 使用 Chroma。")],
                plan=QueryPlan(
                    intent="multi_project",
                    expected_coverage=["agentproject", "myagent"],
                ),
                missing_coverage=["myagent"],
            )

    class DeepSeekStub:
        called = False

        async def stream_chat(self, messages):
            self.called = True
            yield "不应生成"

        @staticmethod
        def estimate_tokens(text):
            return len(text)

    deepseek = DeepSeekStub()
    service = RagService(RetrievalStub(), deepseek, CitationService())

    async def collect_events():
        return [event async for event in service.answer(
            "比较 Agentproject 和 Myagent 的知识索引。",
            conversation_id="conversation-1",
            session=None,
        )]

    events = asyncio.run(collect_events())

    assert deepseek.called is False
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["citations"] == []


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


def test_internship_claim_is_rejected_without_internship_evidence(svc):
    chunks = [_chunk(score=0.72, content="负责个人项目的后端开发")]

    assert svc.has_sufficient_evidence(chunks, question="朱旭在字节跳动实习过吗") is False


def test_project_nature_can_be_proven_by_cooperation_evidence(svc):
    chunks = [
        _chunk(
            score=0.8,
            content="Farino 是南昌大学与法奥机器人的校企合作项目。",
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="Farino 是正式 AI 实习、个人项目，还是校企合作？",
    ) is True


def test_numeric_claim_is_rejected_without_numeric_evidence(svc):
    chunks = [_chunk(score=0.72, content="知识库没有记录该成绩")]

    assert svc.has_sufficient_evidence(chunks, question="朱旭的 GPA 是多少") is False


def test_academic_metrics_require_values_for_the_requested_fields(svc):
    chunks = [
        _chunk(
            score=0.72,
            content="朱旭于 2024 年本科毕业，能够阅读英语技术文档。",
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="朱旭的 GPA、专业排名和英语考试具体分数是多少？",
    ) is False


def test_academic_metrics_accept_values_for_each_requested_field(svc):
    chunks = [
        _chunk(
            score=0.72,
            content="GPA：3.72；专业排名第 8 名；CET-6：531 分。",
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="朱旭的 GPA、专业排名和英语考试具体分数是多少？",
    ) is True


def test_work_location_and_availability_require_field_specific_values(svc):
    chunks = [
        _chunk(
            score=0.72,
            content=(
                "朱旭于 2024 年毕业，有一段实习经历，正在关注上海的技术岗位，"
                "并且每周维护 5 个个人项目。"
            ),
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="朱旭期望在哪个城市工作，什么时候能到岗，每周能实习几天？",
    ) is False


def test_work_location_and_availability_accept_each_requested_value(svc):
    chunks = [
        _chunk(
            score=0.72,
            content="期望工作城市：上海；两周内到岗；每周可实习 5 天。",
            tags=["experience"],
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="朱旭期望在哪个城市工作，什么时候能到岗，每周能实习几天？",
    ) is True


def test_salary_question_rejects_unrelated_numbers(svc):
    chunks = [_chunk(score=0.72, content="候选人完成了 4 个项目和 2 段实践经历。")]

    assert svc.has_sufficient_evidence(
        chunks,
        question="朱旭的期望薪资具体是多少？",
    ) is False


def test_salary_question_accepts_an_explicit_amount(svc):
    chunks = [_chunk(score=0.72, content="期望薪资：18-22k/月。")]

    assert svc.has_sufficient_evidence(
        chunks,
        question="朱旭的期望薪资具体是多少？",
    ) is True


def test_business_usage_question_rejects_unrelated_project_metrics(svc):
    chunks = [
        _chunk(
            score=0.72,
            content="项目有 30 条离线检索样本，Recall@5 达到 93.33%。",
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="Farino 项目实际有多少企业用户、日访问量和正式上线客户？",
    ) is False


def test_business_usage_question_accepts_each_requested_metric(svc):
    chunks = [
        _chunk(
            score=0.72,
            content="企业用户：12 家；日访问量：3.5 万次；正式上线客户：8 家。",
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="Farino 项目实际有多少企业用户、日访问量和正式上线客户？",
    ) is True


def test_production_metrics_reject_offline_benchmark_numbers(svc):
    chunks = [
        _chunk(
            score=0.72,
            content="离线评测集包含 30 条样本，Recall@5 为 93.33%，P95 为 180ms。",
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="Agentproject 在线上生产环境的并发量、SLA 和商业收益分别是多少？",
    ) is False


def test_production_metrics_accept_each_requested_value(svc):
    chunks = [
        _chunk(
            score=0.72,
            content="峰值并发量：120 QPS；SLA：99.95%；商业收益：年节省 80 万元。",
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="Agentproject 在线上生产环境的并发量、SLA 和商业收益分别是多少？",
    ) is True


def test_traffic_and_reliability_require_both_requested_values(svc):
    chunks = [
        _chunk(
            score=0.72,
            content="真实访问用户：1200 人；离线评测 P95 延迟为 180ms。",
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="本站项目已有多少真实访问用户，生产稳定性达到几个九？",
    ) is False


def test_traffic_and_reliability_accept_both_requested_values(svc):
    chunks = [
        _chunk(
            score=0.72,
            content="真实访问用户：1200 人；生产稳定性：99.9%。",
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question="本站项目已有多少真实访问用户，生产稳定性达到几个九？",
    ) is True


def test_agent_offline_metrics_remain_answerable(svc):
    chunks = [
        _chunk(
            score=0.72,
            content=(
                "30 条冻结检索测试样本；Recall@5：93.3%；MRR：0.933；"
                "nDCG@5：0.904；Hybrid 检索 P95：385ms。这些属于小规模离线结果。"
            ),
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question=(
            "Agentproject 的冻结检索集规模、Recall@5、MRR、nDCG@5 和 P95 "
            "结果是多少，这些数字能说明什么边界？"
        ),
    ) is True


def test_mood_tracker_offline_metrics_remain_answerable(svc):
    chunks = [
        _chunk(
            score=0.72,
            content=(
                "测试集 430 条；Accuracy：91.86%；Macro-F1：92.08%；"
                "Weighted-F1：91.84%。结果不能外推到开放场景。"
            ),
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question=(
            "Mood Tracker 的测试集规模和 Accuracy、Macro-F1、Weighted-F1 是多少，"
            "为什么不能外推为开放场景效果？"
        ),
    ) is True


def test_mood_tracker_markdown_test_count_is_metric_evidence(svc):
    chunks = [
        _chunk(
            score=0.72,
            content=(
                "| 测试集 | 430 |\n"
                "在 430 条独立测试样本上，Accuracy：91.86%；"
                "Macro-F1：92.08%；Weighted-F1：91.84%。"
                "测试集规模较小，结果不能直接代表真实开放场景。"
            ),
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question=(
            "Mood Tracker 的测试集有多少条独立样本，模型 Accuracy、"
            "Macro-F1、Weighted-F1 是多少，为什么不能把它当作开放集效果？"
        ),
    ) is True


def test_independent_evaluation_workflow_is_not_a_personal_responsibility_claim(svc):
    chunks = [
        _chunk(
            score=0.72,
            section="评测门禁",
            content=(
                "PR 运行 30 条冻结检索排名和 62 条离线 Agent golden；"
                "真实模型评测由独立工作流定期执行。"
            ),
        )
    ]

    assert svc.has_sufficient_evidence(
        chunks,
        question=(
            "PR 门禁中的 30 条检索案例和 62 条 Agent 案例分别是什么，"
            "为什么真实模型评测要独立运行？"
        ),
    ) is True

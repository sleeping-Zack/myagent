from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from scripts.evaluate_rag import (
    evaluate_quality_gates,
    resolve_source_ids,
    score_case,
    summarize_cases,
    validate_dataset,
)


def _case(**overrides):
    case = {
        "id": "case-01",
        "category": "测试类别",
        "case_type": "factoid",
        "difficulty": "medium",
        "question": "测试问题是什么？",
        "expected_behavior": "evidence",
        "expected_intent": "general",
        "relevance": {"primary.md": 3, "supporting.md": 2, "alternative.md": 1},
        "evidence_groups": [["primary.md"], ["supporting.md", "alternative.md"]],
    }
    case.update(overrides)
    return case


def test_validate_dataset_rejects_duplicate_ids():
    case = _case()
    dataset = {
        "schema_version": 3,
        "dataset_version": "test",
        "name": "test-set",
        "cases": [case, deepcopy(case)],
    }

    with pytest.raises(ValueError, match="重复"):
        validate_dataset(dataset)


def test_validate_dataset_rejects_duplicate_normalized_questions():
    first = _case(id="case-01", question="RAG 的 Top-K 是多少？")
    second = _case(id="case-02", question="RAG的 top_k 是多少")
    dataset = {
        "schema_version": 3,
        "dataset_version": "test",
        "name": "test-set",
        "cases": [first, second],
    }

    with pytest.raises(ValueError, match="question.*重复"):
        validate_dataset(dataset)


def test_validate_dataset_allows_guard_only_protected_case():
    case = _case(
        expected_behavior="protected",
        relevance={},
        evidence_groups=[],
        forbidden_sources=[],
    )
    dataset = {
        "schema_version": 3,
        "dataset_version": "test",
        "name": "test-set",
        "cases": [case],
    }

    validate_dataset(dataset)


def test_score_case_calculates_ranking_coverage_and_duplicate_penalty():
    result = score_case(
        _case(),
        ranked_sources=[
            "noise.md",
            "primary.md",
            "primary.md",
            "supporting.md",
            "other.md",
        ],
        actual_intent="general",
        direct_answer=None,
        latency_ms=12.34,
    )

    assert result["hit_at_1"] == 0.0
    assert result["hit_at_3"] == 1.0
    assert result["hit_at_5"] == 1.0
    assert result["first_relevant_rank"] == 2
    assert result["reciprocal_rank_at_5"] == 0.5
    assert result["evidence_coverage_at_5"] == 1.0
    assert result["complete_evidence_at_5"] == 1.0
    assert result["source_diversity_at_5"] == 0.8
    assert 0.0 < result["ndcg_at_5"] < 1.0


def test_score_case_marks_a_miss_without_moving_results_beyond_cutoff():
    result = score_case(
        _case(evidence_groups=[["primary.md"]]),
        ranked_sources=["n1", "n2", "n3", "n4", "n5", "primary.md"],
        actual_intent="general",
        direct_answer=None,
        latency_ms=1,
    )

    assert result["hit_at_5"] == 0.0
    assert result["reciprocal_rank_at_5"] == 0.0
    assert result["evidence_coverage_at_5"] == 0.0
    assert result["task_success"] == 0.0


def test_score_case_records_retrieval_plan_coverage_diagnostics():
    result = score_case(
        _case(),
        ranked_sources=["primary.md"],
        actual_intent="multi_part",
        direct_answer=None,
        latency_ms=10,
        plan_expected_coverage=["项目", "实习经历"],
        plan_missing_coverage=["实习经历"],
    )

    assert result["plan_expected_coverage"] == ["项目", "实习经历"]
    assert result["plan_missing_coverage"] == ["实习经历"]


@pytest.mark.parametrize(
    ("case", "sources", "direct_answer", "expected_success"),
    [
        (
            _case(
                expected_behavior="direct_answer",
                expected_intent="project_list",
                relevance={},
                evidence_groups=[],
            ),
            [None],
            "项目 A、项目 B",
            1.0,
        ),
        (
            _case(
                expected_behavior="abstain",
                relevance={},
                evidence_groups=[],
                abstention_sources=["missing.md"],
            ),
            [],
            None,
            1.0,
        ),
        (
            _case(
                expected_behavior="abstain",
                relevance={},
                evidence_groups=[],
                abstention_sources=["missing.md"],
            ),
            ["unrelated.md"],
            None,
            0.0,
        ),
        (
            _case(
                expected_behavior="abstain",
                relevance={},
                evidence_groups=[],
                abstention_sources=["missing.md"],
            ),
            ["missing.md"],
            None,
            1.0,
        ),
        (
            _case(
                expected_behavior="protected",
                relevance={},
                evidence_groups=[],
                forbidden_sources=["private.md"],
            ),
            ["public.md"],
            None,
            1.0,
        ),
        (
            _case(
                expected_behavior="protected",
                relevance={},
                evidence_groups=[],
                forbidden_sources=["private.md"],
            ),
            ["private.md"],
            None,
            0.0,
        ),
    ],
)
def test_score_case_handles_non_evidence_behaviors(
    case, sources, direct_answer, expected_success
):
    result = score_case(
        case,
        ranked_sources=sources,
        actual_intent=case["expected_intent"],
        direct_answer=direct_answer,
        latency_ms=2,
        input_rejected=case["expected_behavior"] == "protected",
    )

    assert result["task_success"] == expected_success
    assert result["hit_at_5"] is None


def test_protected_case_requires_input_rejection_even_when_sources_are_isolated():
    result = score_case(
        _case(
            expected_behavior="protected",
            relevance={},
            evidence_groups=[],
            forbidden_sources=["private.md"],
        ),
        ranked_sources=["public.md"],
        actual_intent="general",
        direct_answer=None,
        latency_ms=2,
        input_rejected=False,
    )

    assert result["task_success"] == 0.0
    assert result["protected_source_leakage"] is False


def test_guard_only_protected_case_does_not_count_as_source_probe():
    result = score_case(
        _case(
            expected_behavior="protected",
            relevance={},
            evidence_groups=[],
            forbidden_sources=[],
        ),
        ranked_sources=["public.md"],
        actual_intent="general",
        direct_answer=None,
        latency_ms=2,
        input_rejected=True,
    )

    assert result["task_success"] == 1.0
    assert result["source_isolation_probe"] is False


def test_benign_case_fails_when_the_input_guard_rejects_it():
    result = score_case(
        _case(),
        ranked_sources=["primary.md", "supporting.md"],
        actual_intent="general",
        direct_answer=None,
        latency_ms=2,
        input_rejected=True,
    )

    assert result["complete_evidence_at_5"] == 1.0
    assert result["task_success"] == 0.0


def test_summarize_cases_uses_behavior_specific_denominators():
    evidence = score_case(
        _case(),
        ["primary.md", "supporting.md"],
        actual_intent="general",
        direct_answer=None,
        latency_ms=10,
    )
    abstain = score_case(
        _case(
            expected_behavior="abstain",
            relevance={},
            evidence_groups=[],
            abstention_sources=["missing.md"],
        ),
        [],
        actual_intent="general",
        direct_answer=None,
        latency_ms=30,
    )
    protected = score_case(
        _case(
            expected_behavior="protected",
            relevance={},
            evidence_groups=[],
            forbidden_sources=["private.md"],
        ),
        ["public.md"],
        actual_intent="general",
        direct_answer=None,
        latency_ms=20,
        input_rejected=True,
    )

    metrics = summarize_cases([evidence, abstain, protected])

    assert metrics["task_success_rate"] == 1.0
    assert metrics["hit_rate_at_5"] == 1.0
    assert metrics["knowledge_boundary_accuracy"] == 1.0
    assert metrics["benign_query_allow_rate"] == 1.0
    assert metrics["protected_query_block_rate"] == 1.0
    assert metrics["protected_source_leakage_rate"] == 0.0
    assert metrics["protected_source_probe_count"] == 1
    assert metrics["p50_retrieval_latency_ms"] == 20.0
    assert metrics["p95_retrieval_latency_ms"] == 30.0


def test_boundary_source_supports_a_safe_refusal_without_factual_evidence():
    boundary = score_case(
        _case(
            expected_behavior="abstain",
            relevance={},
            evidence_groups=[],
            abstention_sources=["missing.md"],
        ),
        ["missing.md"],
        actual_intent="general",
        direct_answer=None,
        latency_ms=5,
        evidence_sufficient=False,
    )

    metrics = summarize_cases([boundary])

    assert boundary["task_success"] == 1.0
    assert boundary["evidence_sufficient"] is False
    assert metrics["evidence_decision_accuracy"] == 1.0
    assert metrics["evidence_decision_f1"] == 1.0
    assert metrics["unsupported_answer_rate"] == 0.0


def test_quality_gate_reports_each_failed_metric():
    gate = evaluate_quality_gates(
        {
            "hit_rate_at_5": 0.84,
            "mrr_at_5": 0.90,
            "ndcg_at_5": 0.90,
            "evidence_coverage_at_5": 0.90,
            "planner_intent_accuracy": 1.0,
            "evidence_decision_f1": 0.95,
            "knowledge_boundary_accuracy": 1.0,
            "task_success_rate": 0.90,
            "unsupported_answer_rate": 0.0,
            "benign_query_allow_rate": 1.0,
            "protected_query_block_rate": 1.0,
            "protected_source_leakage_rate": 0.0,
        }
    )

    assert gate["passed"] is False
    assert [check["metric"] for check in gate["checks"] if not check["passed"]] == [
        "hit_rate_at_5"
    ]


def test_source_ids_are_resolved_from_chunk_provenance():
    first_id = uuid4()
    second_id = uuid4()
    query_result = MagicMock()
    query_result.all.return_value = [
        SimpleNamespace(id=first_id, source_id="knowledge/projects/agentproject.md"),
        SimpleNamespace(
            id=second_id, source_id="knowledge\\07_technical_interview_qa.md"
        ),
    ]
    session = AsyncMock()
    session.execute.return_value = query_result

    import asyncio

    sources = asyncio.run(
        resolve_source_ids(
            session,
            [
                {"chunk_id": str(first_id)},
                {"chunk_id": "structured-project-list"},
                {"chunk_id": str(second_id)},
            ],
        )
    )

    assert sources == [
        "projects/agentproject.md",
        None,
        "07_technical_interview_qa.md",
    ]
